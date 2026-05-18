import os
from concurrent.futures import ThreadPoolExecutor
from django.core.cache import cache
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from .models import Product, Order, OrderItem
from .serializers import (
    ProductSerializer,
    OrderSerializer,
    OrderItemSerializer,
    CreateOrderSerializer,
)
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.response import Response
from .serializers import RegisterSerializer
from rest_framework import status
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.db.models import F
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)

n_cores = os.cpu_count() or 1

IO_WORKERS = n_cores * 5
io_executor = ThreadPoolExecutor(max_workers=IO_WORKERS, thread_name_prefix="IO_Worker")

CPU_WORKERS = n_cores + 1
cpu_executor = ThreadPoolExecutor(
    max_workers=CPU_WORKERS, thread_name_prefix="CPU_Worker"
)


def send_email_notification(order_id):

    print(f"Running Email Task in thread: {threading.current_thread().name}")

    # محاكاة عملية ارسال ايميل
    time.sleep(3)

    print(f"Email sent successfully for order {order_id}")


def generate_invoice(order_id):

    print(f"Running Invoice Task in thread: {threading.current_thread().name}")

    total = 0

    for i in range(10_000_000):
        total += i

    print(f"Invoice generated for order {order_id}")


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def register(request):
    serializer = RegisterSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    def save_task(valid_ser):
        valid_ser.save()

    io_executor.submit(save_task, serializer)

    return Response(
        {"message": "User registration is being processed successfully"},
        status=status.HTTP_202_ACCEPTED,
    )


class ProductListCreateAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):

        cached_data = cache.get("products_list_cache")

        if cached_data:

            io_executor.submit(self.refresh_cache)
            return Response(cached_data)
        data = self.refresh_cache()
        return Response(data)

    def post(self, request):
        serializer = ProductSerializer(data=request.data)
        if serializer.is_valid():

            def save_product():
                serializer.save()
                self.refresh_cache()

            io_executor.submit(save_product)
            return Response(
                {"message": "Product is being created"}, status=status.HTTP_202_ACCEPTED
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def refresh_cache(self):
        #   time.sleep(2)
        products = Product.objects.all()
        serializer = ProductSerializer(products, many=True)
        data = serializer.data
        cache.set("products_list_cache", data, 60)
        return data


class ProductDetailAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get_object(self, id):
        try:
            return Product.objects.get(id=id)
        except Product.DoesNotExist:
            return None

    def get(self, request, id):
        product = self.get_object(id)
        if not product:
            return Response({"error": "Not found"}, status=404)

        serializer = ProductSerializer(product)
        return Response(serializer.data)

    def put(self, request, id):
        product = self.get_object(id)
        if not product:
            return Response({"error": "Not found"}, status=404)

        serializer = ProductSerializer(product, data=request.data)

        if serializer.is_valid():

            def run_save():
                serializer.save()

            io_executor.submit(run_save)
            return Response({"message": "Product is being updated"}, status=202)

        return Response(serializer.errors, status=400)

    def delete(self, request, id):
        product = self.get_object(id)
        if not product:
            return Response({"error": "Not found"}, status=404)

        def run_delete():
            product.delete()

        io_executor.submit(run_delete)
        return Response({"message": "Product deletion is being processed"}, status=202)


class OrderListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CreateOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        product_id = serializer.validated_data["product_id"]
        quantity = serializer.validated_data["quantity"]

        if quantity <= 0:
            return Response({"error": "Invalid quantity"}, status=400)

        def run_create_order_logic(user):
            try:
                with transaction.atomic():
                    updated = Product.objects.filter(
                        id=product_id, stock__gte=quantity
                    ).update(stock=F("stock") - quantity)

                    if not updated:
                        print(f"Stock insufficient for product {product_id}")
                        return

                    order = Order.objects.create(user=user)
                    OrderItem.objects.create(
                        order=order, product_id=product_id, quantity=quantity
                    )

                io_executor.submit(send_email_notification, order.id)

            except Exception as e:
                print(f"Error in background task: {e}")

        io_executor.submit(run_create_order_logic, request.user)

        return Response(
            {"message": "Order processing started"}, status=status.HTTP_202_ACCEPTED
        )


class OrderDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, id):
        order = get_object_or_404(Order, id=id, user=request.user)
        serializer = OrderSerializer(order)
        return Response(serializer.data)

    def put(self, request, id):
        order = get_object_or_404(Order, id=id, user=request.user)

        def run_put_logic():
            with transaction.atomic():
                order_bg = Order.objects.get(id=id)
                item = order_bg.orderitem_set.select_for_update().first()
                product = item.product

                new_quantity = request.data.get("quantity")
                if not new_quantity:
                    return

                new_quantity = int(new_quantity)
                product = item.product

                # نحسب الفرق
                diff = new_quantity - item.quantity

                if diff > 0 and product.stock < diff:
                    return

                # نعدل المخزون
                product.stock -= diff
                product.save()

                # نعدل الطلب
                item.quantity = new_quantity
                item.save()

        io_executor.submit(run_put_logic)
        return Response({"message": "Order update is being processed"}, status=202)

    def delete(self, request, id):
        order = get_object_or_404(Order, id=id, user=request.user)

        def run_delete_logic():
            with transaction.atomic():
                order_bg = Order.objects.get(id=id)
                item = order_bg.orderitem_set.select_for_update().first()
                product = item.product

                # رجع الكمية للمخزون
                product.stock += item.quantity
                product.save()

                order_bg.delete()

        io_executor.submit(run_delete_logic)
        return Response({"message": "Order deleted"}, status=202)


# class PayOrderAPIView(APIView):
#     def post(self, request, id):
#         order = get_object_or_404(Order, id=id, user=request.user)
#         def process_payment():
# #حطيت قيمة سليب 2 لحتى يحاكي عملية الدفع
#             time.sleep(2)
#             order.status = 'PAID'
#             order.save()
#             # CPU intensive task
# cpu_executor.submit(generate_invoice,order.id)
#         io_executor.submit(process_payment)
#         return Response({"message": "Payment sent for processing"}, status=202)
class PayOrderAPIView(APIView):

    def post(self, request, id):

        order = get_object_or_404(Order, id=id, user=request.user)

        def process_payment():

            # محاكاة عملية الدفع
            time.sleep(2)

            order.status = "PAID"
            order.save()

            cpu_executor.submit(generate_invoice, order.id)

        io_executor.submit(process_payment)

        return Response({"message": "Payment sent for processing"}, status=202)


class CompleteOrderAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, id):
        order = get_object_or_404(Order, id=id, user=request.user)

        if order.status != "PAID":
            return Response({"error": "Order not paid"}, status=400)

        def run_complete_logic():
            order.status = "COMPLETED"
            order.save()

        io_executor.submit(run_complete_logic)
        return Response({"message": "Order completion is being processed"}, status=202)


class CancelOrderAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, id):
        order = get_object_or_404(Order, id=id, user=request.user)

        if order.status == "CANCELLED":
            return Response({"error": "Already cancelled"}, status=400)

        def run_cancel_logic():
            with transaction.atomic():
                order_bg = Order.objects.get(id=id)
                item = order_bg.orderitem_set.select_for_update().first()
                if item:
                    product = item.product

                    # رجع المخزون
                    product.stock += item.quantity
                    product.save()

                order_bg.status = "CANCELLED"
                order_bg.save()

        io_executor.submit(run_cancel_logic)
        return Response(
            {"message": "Order cancellation is being processed"}, status=202
        )


class BulkDataChargerAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        from django.contrib.auth import get_user_model
        from .models import Order, Product, OrderItem
        from django.utils import timezone

        User = get_user_model()
        user = User.objects.first()
        product = Product.objects.first()

        if not user or not product:
            return Response(
                {"error": "Ensure you have at least one user and one product in DB"},
                status=400,
            )

        print(" Starting Bulk Data Injection...")

        orders_to_create = [
            Order(user=user, status="PAID", created_at=timezone.now())
            for _ in range(50000)
        ]
        created_orders = Order.objects.bulk_create(orders_to_create)

        order_items_to_create = [
            OrderItem(order=order, product=product, quantity=2)
            for order in created_orders
        ]
        OrderItem.objects.bulk_create(order_items_to_create)

        print(" Successfully injected 50000 paid orders into PostgreSQL!")
        return Response(
            {"message": "Successfully injected 50000 paid orders for benchmarking!"},
            status=201,
        )
