"""Sorting algorithms as step generators (all work on a private copy)."""

from __future__ import annotations

from collections.abc import Iterator

from core.registry import algo
from core.steps import BarStep, Tally

CAT = "Sorting"


def _done(data: list[int], tally: Tally, label: str = "Sorted ascending") -> BarStep:
    return BarStep(
        data=tuple(data),
        sorted_idx=frozenset(range(len(data))),
        is_key=True,
        label=label,
        stats=tally.snapshot(),
    )


@algo("bubble", "Bubble Sort", CAT, "bars")
def bubble_sort(values: list[int]) -> Iterator[BarStep]:
    a = list(values)
    n = len(a)
    t = Tally("compares", "swaps")
    done: set[int] = set()
    yield BarStep(data=tuple(a), is_key=True, label="Start", stats=t.snapshot())
    for p in range(n - 1):
        swapped = False
        for i in range(n - 1 - p):
            t.add("compares")
            yield BarStep(
                data=tuple(a),
                compare=(i, i + 1),
                sorted_idx=frozenset(done),
                label=f"Pass {p + 1}: compare",
                stats=t.snapshot(),
            )
            if a[i] > a[i + 1]:
                a[i], a[i + 1] = a[i + 1], a[i]
                swapped = True
                t.add("swaps")
                yield BarStep(
                    data=tuple(a),
                    swap=(i, i + 1),
                    sorted_idx=frozenset(done),
                    label=f"Pass {p + 1}: swap",
                    stats=t.snapshot(),
                )
        done.add(n - 1 - p)
        if not swapped:
            break
        if len(done) < n:
            yield BarStep(
                data=tuple(a),
                sorted_idx=frozenset(done),
                is_key=True,
                label=f"Pass {p + 1} done",
                stats=t.snapshot(),
            )
    yield _done(a, t)


@algo("selection", "Selection Sort", CAT, "bars")
def selection_sort(values: list[int]) -> Iterator[BarStep]:
    a = list(values)
    n = len(a)
    t = Tally("compares", "swaps")
    yield BarStep(data=tuple(a), is_key=True, label="Start", stats=t.snapshot())
    for i in range(n - 1):
        low = i
        for j in range(i + 1, n):
            t.add("compares")
            yield BarStep(
                data=tuple(a),
                compare=(low, j),
                pivot=low,
                sorted_idx=frozenset(range(i)),
                label=f"Find minimum from index {i}",
                stats=t.snapshot(),
            )
            if a[j] < a[low]:
                low = j
        if low != i:
            a[i], a[low] = a[low], a[i]
            t.add("swaps")
        yield BarStep(
            data=tuple(a),
            swap=(i, low) if low != i else None,
            sorted_idx=frozenset(range(i + 1)),
            is_key=True,
            label=f"Place {a[i]} at index {i}",
            stats=t.snapshot(),
        )
    yield _done(a, t)


@algo("insertion", "Insertion Sort", CAT, "bars")
def insertion_sort(values: list[int]) -> Iterator[BarStep]:
    a = list(values)
    n = len(a)
    t = Tally("compares", "swaps")
    yield BarStep(
        data=tuple(a),
        sorted_idx=frozenset({0}),
        is_key=True,
        label="Start (first item is a sorted run)",
        stats=t.snapshot(),
    )
    for i in range(1, n):
        j = i
        while j > 0:
            t.add("compares")
            yield BarStep(
                data=tuple(a),
                compare=(j - 1, j),
                sorted_idx=frozenset(range(i)),
                label=f"Insert {a[j]}: compare",
                stats=t.snapshot(),
            )
            if a[j - 1] <= a[j]:
                break
            a[j - 1], a[j] = a[j], a[j - 1]
            t.add("swaps")
            yield BarStep(
                data=tuple(a),
                swap=(j - 1, j),
                sorted_idx=frozenset(range(i)),
                label=f"Insert {a[j - 1]}: shift left",
                stats=t.snapshot(),
            )
            j -= 1
        yield BarStep(
            data=tuple(a),
            sorted_idx=frozenset(range(i + 1)),
            is_key=True,
            label=f"Inserted item {i + 1} of {n}",
            stats=t.snapshot(),
        )
    yield _done(a, t)


@algo("quick", "Quick Sort", CAT, "bars")
def quick_sort(values: list[int]) -> Iterator[BarStep]:
    a = list(values)
    t = Tally("compares", "swaps")
    done: set[int] = set()
    yield BarStep(data=tuple(a), is_key=True, label="Start", stats=t.snapshot())
    # Explicit stack: no recursion, so input size can never overflow the stack.
    stack: list[tuple[int, int]] = [(0, len(a) - 1)]
    while stack:
        lo, hi = stack.pop()
        if lo > hi:
            continue
        if lo == hi:
            done.add(lo)
            continue
        pivot = a[hi]  # Lomuto partition, last element as pivot
        store = lo
        for i in range(lo, hi):
            t.add("compares")
            yield BarStep(
                data=tuple(a),
                compare=(i, hi),
                pivot=hi,
                active_range=(lo, hi),
                sorted_idx=frozenset(done),
                label=f"Partition [{lo}..{hi}] around {pivot}",
                stats=t.snapshot(),
            )
            if a[i] < pivot:
                if i != store:
                    a[i], a[store] = a[store], a[i]
                    t.add("swaps")
                    yield BarStep(
                        data=tuple(a),
                        swap=(i, store),
                        pivot=hi,
                        active_range=(lo, hi),
                        sorted_idx=frozenset(done),
                        label="Move smaller item left",
                        stats=t.snapshot(),
                    )
                store += 1
        if store != hi:
            a[store], a[hi] = a[hi], a[store]
            t.add("swaps")
        done.add(store)
        yield BarStep(
            data=tuple(a),
            swap=(store, hi) if store != hi else None,
            pivot=store,
            active_range=(lo, hi),
            sorted_idx=frozenset(done),
            is_key=True,
            label=f"Pivot {pivot} placed at index {store}",
            stats=t.snapshot(),
        )
        stack.append((store + 1, hi))
        stack.append((lo, store - 1))
    yield _done(a, t)


@algo("heap", "Heap Sort", CAT, "bars")
def heap_sort(values: list[int]) -> Iterator[BarStep]:
    a = list(values)
    n = len(a)
    t = Tally("compares", "swaps")
    yield BarStep(data=tuple(a), is_key=True, label="Start", stats=t.snapshot())

    def sift_down(root: int, size: int) -> Iterator[BarStep]:
        while True:
            largest = root
            for child in (2 * root + 1, 2 * root + 2):
                if child < size:
                    t.add("compares")
                    yield BarStep(
                        data=tuple(a),
                        compare=(largest, child),
                        heap_size=size,
                        sorted_idx=frozenset(range(size, n)),
                        label="Sift down: compare with child",
                        stats=t.snapshot(),
                    )
                    if a[child] > a[largest]:
                        largest = child
            if largest == root:
                return
            a[root], a[largest] = a[largest], a[root]
            t.add("swaps")
            yield BarStep(
                data=tuple(a),
                swap=(root, largest),
                heap_size=size,
                sorted_idx=frozenset(range(size, n)),
                label="Sift down: swap",
                stats=t.snapshot(),
            )
            root = largest

    for start in range(n // 2 - 1, -1, -1):
        yield from sift_down(start, n)
    yield BarStep(
        data=tuple(a),
        heap_size=n,
        is_key=True,
        label="Max-heap built (largest at index 0)",
        stats=t.snapshot(),
    )
    for end in range(n - 1, 0, -1):
        a[0], a[end] = a[end], a[0]
        t.add("swaps")
        yield BarStep(
            data=tuple(a),
            swap=(0, end),
            heap_size=end,
            sorted_idx=frozenset(range(end, n)),
            label=f"Move max {a[end]} to index {end}",
            stats=t.snapshot(),
        )
        yield from sift_down(0, end)
        yield BarStep(
            data=tuple(a),
            heap_size=end,
            sorted_idx=frozenset(range(end, n)),
            is_key=True,
            label=f"Extracted {a[end]}; heap size {end}",
            stats=t.snapshot(),
        )
    yield _done(a, t)


@algo("merge", "Merge Sort", CAT, "bars")
def merge_sort(values: list[int]) -> Iterator[BarStep]:
    a = list(values)
    n = len(a)
    t = Tally("compares", "writes")
    yield BarStep(data=tuple(a), is_key=True, label="Start", stats=t.snapshot())

    def sort(lo: int, hi: int) -> Iterator[BarStep]:
        # Recursion depth is log2(n) <= 5 for the enforced size limit.
        if lo >= hi:
            return
        mid = (lo + hi) // 2
        yield from sort(lo, mid)
        yield from sort(mid + 1, hi)
        buf = a[lo : hi + 1]  # copy of the two sorted halves
        left, right = 0, mid - lo + 1
        left_end, right_end = right, len(buf)
        k = lo
        while left < left_end or right < right_end:
            pair: tuple[int, int] | None = None
            if left < left_end and right < right_end:
                t.add("compares")
                pair = (left, right)
                take_left = buf[left] <= buf[right]
            else:
                take_left = left < left_end
            if take_left:
                a[k] = buf[left]
                left += 1
            else:
                a[k] = buf[right]
                right += 1
            t.add("writes")
            yield BarStep(
                data=tuple(a),
                focus=k,
                active_range=(lo, hi),
                aux=tuple(buf),
                aux_compare=pair,
                label=f"Merge [{lo}..{hi}]: write index {k}",
                stats=t.snapshot(),
            )
            k += 1
        yield BarStep(
            data=tuple(a),
            active_range=(lo, hi),
            is_key=True,
            label=f"Merged [{lo}..{hi}]",
            stats=t.snapshot(),
        )

    yield from sort(0, n - 1)
    yield _done(a, t)


@algo("radix", "Radix Sort", CAT, "bars")
def radix_sort(values: list[int]) -> Iterator[BarStep]:
    a = list(values)
    t = Tally("passes", "moves")
    yield BarStep(data=tuple(a), is_key=True, label="Start", stats=t.snapshot())
    place = 1
    pass_no = 0
    while place <= max(a):
        pass_no += 1
        name = {1: "ones", 10: "tens"}.get(place, f"{place}s")
        buckets: list[list[int]] = [[] for _ in range(10)]
        for i, value in enumerate(a):
            digit = (value // place) % 10
            buckets[digit].append(value)
            t.add("moves")
            yield BarStep(
                data=tuple(a),
                focus=i,
                buckets=tuple(tuple(b) for b in buckets),
                label=f"Pass {pass_no} ({name} digit): {value} -> bucket {digit}",
                stats=t.snapshot(),
            )
        a = [value for bucket in buckets for value in bucket]
        remaining = [list(b) for b in buckets]
        collected = 0
        for digit, bucket in enumerate(buckets):
            if not bucket:
                continue
            collected += len(bucket)
            remaining[digit] = []
            yield BarStep(
                data=tuple(a),
                active_range=(0, collected - 1),
                buckets=tuple(tuple(b) for b in remaining),
                label=f"Pass {pass_no}: collect bucket {digit}",
                stats=t.snapshot(),
            )
        t.add("passes")
        yield BarStep(
            data=tuple(a),
            is_key=True,
            label=f"Pass {pass_no} ({name} digit) done",
            stats=t.snapshot(),
        )
        place *= 10
    yield _done(a, t)
