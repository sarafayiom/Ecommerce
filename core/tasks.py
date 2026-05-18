from .models import OrderItem
from django.utils import timezone
import time
from .views import cpu_executor


def process_chunk_task(batch_data, chunk_num):
    chunk_revenue = 0
    for item in batch_data:
        chunk_revenue += item.quantity * item.product.price
    print(f" [Parallel Worker] Chunk #{chunk_num} Finished Processing !")
    return chunk_revenue


def process_daily_sales_chunks():

    print(f"  Starting Sales Benchmarking  ")

    today = timezone.now().date()

    BATCH_SIZE = 1000

    queryset = (
        OrderItem.objects.filter(order__status="PAID", order__created_at__date=today)
        .select_related("product")
        .order_by("id")
    )

    total_items = queryset.count()

    if total_items == 0:
        print(
            " No paid orders found for today to benchmark. Please run Bulk Charger first!"
        )
        return

    print(
        f"\n  Processing began without partitioning all data ({total_items} register)..."
    )

    start_normal = time.time()

    sales_list_normal = list(queryset)

    total_revenue_normal = 0
    processed_count_normal = 0

    for item in sales_list_normal:
        item_total = item.quantity * item.product.price
        total_revenue_normal += item_total
        processed_count_normal += 1

    end_normal = time.time()

    duration_normal = end_normal - start_normal

    print(f" Processing output without division:")

    print(f" Number of requests processed: {processed_count_normal}")

    print(f" Final price of orders (Total Revenue): {total_revenue_normal:.2f}")

    print(f" Total time consumed: {duration_normal:.4f} s")

    # WITH CHUNKS PROCESSING

    print(f"\n  Processing began by splitting the data into batches: {BATCH_SIZE}...")

    start_chunks = time.time()
    futures = []
    chunk_index = 0

    for start in range(0, total_items, BATCH_SIZE):

        chunk_index += 1

        batch = list(queryset[start : start + BATCH_SIZE])
        future = cpu_executor.submit(process_chunk_task, batch, chunk_index)
        futures.append(future)
       

    total_revenue_chunks = sum(f.result() for f in futures)
    processed_count_chunks = total_items
    end_chunks = time.time()
    duration_chunks = end_chunks - start_chunks

    print(f"\n Processing outputs with segmentation:")

    print(f"   Number of batches processed  (Total Chunks): {chunk_index}")

    print(f"   Number of requests processed: {processed_count_chunks}")

    print(f"   Final price for orders: {total_revenue_chunks:.2f}")

    print(f"   Final time consumed: {duration_chunks:.4f} s")

    # BENCHMARK RESULT

    print(f"\n  [BENCHMARK RESULT]")

    difference = duration_normal - duration_chunks

    if difference > 0:

        print(f" Batch Processing it was faster by a factor of " f"{difference:.4f} s")

    else:

        print(
            f"Traditional Processing it was faster by a factor of  "
            f"{abs(difference):.4f} s"
        )

    print(f"\n  Batch Benchmark Finished Successfully \n")
