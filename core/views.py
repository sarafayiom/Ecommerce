import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from django.core.cache import cache
from django.db import transaction
from django.db.models import F
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Order, OrderItem, Product
from .serializers import (
    CreateOrderSerializer,
    OrderItemSerializer,
    OrderSerializer,
    ProductSerializer,
    RegisterSerializer,
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

    # def get(self, request):

    #     cached_data = cache.get("products_list_cache")

    #     if cached_data:

    #         io_executor.submit(self.refresh_cache)
    #         return Response(cached_data)
    #     data = self.refresh_cache()
    #     return Response(data)

    def get(self, request):
        cached = cache.get("products:list")
        if cached is not None:
            response = Response(cached)
            response["X-Cache"] = "HIT"
            return response

        products = Product.objects.all()
        data = ProductSerializer(products, many=True).data

        cache.set("products:list", data, timeout=60)

        response = Response(data)
        response["X-Cache"] = "MISS"
        return response

    # def post(self, request):
    #     serializer = ProductSerializer(data=request.data)
    #     if serializer.is_valid():

    #         def save_product():
    #             serializer.save()
    #             self.refresh_cache()

    #         io_executor.submit(save_product)
    #         return Response(
    #             {"message": "Product is being created"}, status=status.HTTP_202_ACCEPTED
    #         )

    #     return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def post(self, request):
        serializer = ProductSerializer(data=request.data)
        if serializer.is_valid():

            def save_product():
                serializer.save()
                cache.delete("products:list")  # ← مهم جدًا

            io_executor.submit(save_product)
            return Response({"message": "Product is being created"}, status=201)

        return Response(serializer.errors, status=400)

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

    # def get(self, request, id):
    #     product = self.get_object(id)
    #     if not product:
    #         return Response({"error": "Not found"}, status=404)

    #     serializer = ProductSerializer(product)
    #     return Response(serializer.data)

    def get(self, request, id):
        key = f"product:{id}"
        cached = cache.get(key)

        if cached is not None:
            response = Response(cached)
            response["X-Cache"] = "HIT"
            return response

        product = self.get_object(id)
        if not product:
            return Response({"error": "Not found"}, status=404)

        data = ProductSerializer(product).data
        cache.set(key, data, timeout=120)

        response = Response(data)
        response["X-Cache"] = "MISS"
        return response

    # def put(self, request, id):
    #     product = self.get_object(id)
    #     if not product:
    #         return Response({"error": "Not found"}, status=404)

    #     serializer = ProductSerializer(product, data=request.data)

    #     if serializer.is_valid():

    #         def run_save():
    #             serializer.save()

    #         io_executor.submit(run_save)
    #         return Response({"message": "Product is being updated"}, status=202)

    #     return Response(serializer.errors, status=400)

    def put(self, request, id):
        product = self.get_object(id)
        if not product:
            return Response({"error": "Not found"}, status=404)

        serializer = ProductSerializer(product, data=request.data)

        if serializer.is_valid():

            def run_save():
                serializer.save()
                cache.delete("products:list")
                cache.delete(f"product:{id}")

            io_executor.submit(run_save)
            return Response({"message": "Product is being updated"}, status=202)

        return Response(serializer.errors, status=400)

    # def delete(self, request, id):
    #     product = self.get_object(id)
    #     if not product:
    #         return Response({"error": "Not found"}, status=404)

    #     def run_delete():
    #         product.delete()

    #     io_executor.submit(run_delete)
    #     return Response({"message": "Product deletion is being processed"}, status=202)


    def delete(self, request, id):
        product = self.get_object(id)
        if not product:
            return Response({"error": "Not found"}, status=404)

        def run_delete():
            product.delete()
            cache.delete("products:list")
            cache.delete(f"product:{id}")

        io_executor.submit(run_delete)
        return Response(
            {"message": "Product deletion is being processed"}, status=202
        )



# class OrderListCreateAPIView(APIView):
#     permission_classes = [IsAuthenticated]

#     def post(self, request):
#         serializer = CreateOrderSerializer(data=request.data)
#         serializer.is_valid(raise_exception=True)

#         product_id = serializer.validated_data["product_id"]
#         quantity = serializer.validated_data["quantity"]

#         if quantity <= 0:
#             return Response({"error": "Invalid quantity"}, status=400)

        # def run_create_order_logic(user):
        #     try:
        #         with transaction.atomic():
        #             updated = Product.objects.filter(
        #                 id=product_id, stock__gte=quantity
        #             ).update(stock=F("stock") - quantity)

        #             if not updated:
        #                 print(f"Stock insufficient for product {product_id}")
        #                 return

        #             order = Order.objects.create(user=user)
        #             OrderItem.objects.create(
        #                 order=order, product_id=product_id, quantity=quantity
        #             )

        #         io_executor.submit(send_email_notification, order.id)

        #     except Exception as e:
        #         print(f"Error in background task: {e}")

        # io_executor.submit(run_create_order_logic, request.user)

        # return Response(
        #     {"message": "Order processing started"}, status=status.HTTP_202_ACCEPTED
        # )

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
            lock_key = f"lock:product:{product_id}"

            print("TRY LOCK:", product_id)
            acquired = cache.add(lock_key, "1", timeout=10)
            print("LOCK RESULT:", acquired)

            if not acquired:
                print("Product is locked by another request")
                return

            try:
                with transaction.atomic():
                    updated = Product.objects.filter(
                        id=product_id, stock__gte=quantity
                    ).update(
                        stock=F("stock") - quantity,
                        sold_count=F("sold_count") + 1,
                    )

                    if not updated:
                        print("Not enough stock")
                        return

                    order = Order.objects.create(user=user)

                    OrderItem.objects.create(
                        order=order, product_id=product_id, quantity=quantity
                    )

               #هون ضفت فكرة انو بعد نجاح العملية نسمح الكاش مشان فورا الشخص يلي بعده يحصل على الكمية المحدثة مو السابقة
                cache.delete("products:list")
                cache.delete(f"product:{product_id}")
                cache.delete("products:top10")

                io_executor.submit(send_email_notification, order.id)

            except Exception as e:
                print(f"Error in background task: {e}")

            finally:
                # مهم جداً: تحرير الـ lock
                cache.delete(lock_key)

        # تشغيل الـ task
        io_executor.submit(run_create_order_logic, request.user)

        return Response(
            {"message": "Order processing started"},
            status=status.HTTP_202_ACCEPTED,
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

               # نفس الشي حذفنا الكاش بعد العملية
                cache.delete("products:list")
                cache.delete(f"product:{product.id}")

        io_executor.submit(run_put_logic)
        return Response(
            {"message": "Order update is being processed"}, status=202
        )

    def delete(self, request, id):
        order = get_object_or_404(Order, id=id, user=request.user)

        def run_delete_logic():
            with transaction.atomic():
                order_bg = Order.objects.get(id=id)
                item = order_bg.orderitem_set.select_for_update().first()
                if item:
                    product = item.product

                    # رجع الكمية للمخزون
                    product.stock += item.quantity
                    product.save()

                    # كمان نظفنا الكاش هون
                    cache.delete("products:list")
                    cache.delete(f"product:{product.id}")

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

        return Response(
            {"message": "Payment sent for processing"}, status=202
        )


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
        return Response(
            {"message": "Order completion is being processed"}, status=202
        )


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

                    # كمان هون نظفنا الكاش
                    cache.delete(f"product:{product.id}")
                    cache.delete("products:top10")

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

        from .models import Order, OrderItem, Product

        User = get_user_model()
        user = User.objects.first()
        product = Product.objects.first()

        if not user or not product:
            return Response(
                {
                    "error": "Ensure you have at least one user and one product in DB"
                },
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
            {
                "message": "Successfully injected 50000 paid orders for benchmarking!"
            },
            status=201,
        )


class TopProductsAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        CACHE_KEY = "products:top10"

        cached = cache.get(CACHE_KEY)
        if cached is not None:
            response = Response(cached)
            response["X-Cache"] = "HIT"
            return response

        products = Product.objects.order_by("-sold_count")[:10]
        data = ProductSerializer(products, many=True).data

        cache.set(CACHE_KEY, data, timeout=300)

        response = Response(data)
        response["X-Cache"] = "MISS"
        return response


class CheckoutAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CreateOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        product_id = serializer.validated_data["product_id"]
        quantity = serializer.validated_data["quantity"]

        if quantity <= 0:
            return Response({"error": "Invalid quantity"}, status=400)

        def run_checkout(user):
            lock_key = f"lock:product:{product_id}"

            # 🔐 Distributed Lock
            acquired = cache.add(lock_key, "locked", timeout=10)

            if not acquired:
                print("Product is locked by another request")
                return

            try:
                with transaction.atomic():
                    # 1️⃣ تحديث المخزون
                    updated = Product.objects.filter(
                        id=product_id, stock__gte=quantity
                    ).update(
                        stock=F("stock") - quantity,
                        sold_count=F("sold_count") + 1,
                    )

                    if not updated:
                        print("Not enough stock")
                        return

                    # 2️⃣ إنشاء الطلب
                    order = Order.objects.create(user=user)

                    OrderItem.objects.create(
                        order=order, product_id=product_id, quantity=quantity
                    )

                    # 3️⃣ 💳 الدفع (Mock داخل نفس transaction)
                    time.sleep(1)  # محاكاة دفع
                    order.status = "PAID"
                    order.save()

                # 4️⃣ تنظيف الكاش بعد النجاح
                cache.delete("products:list")
                cache.delete(f"product:{product_id}")
                cache.delete("products:top10")

                # 5️⃣ async email
                io_executor.submit(send_email_notification, order.id)

                print("CHECKOUT SUCCESS ✔")

            except Exception as e:
                print(f"Checkout error: {e}")

            finally:
                # 🔓 تحرير القفل
                cache.delete(lock_key)

        io_executor.submit(run_checkout, request.user)

        return Response(
            {"message": "Checkout processing started"},
            status=status.HTTP_202_ACCEPTED,
        )