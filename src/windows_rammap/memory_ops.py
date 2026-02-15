import ctypes
from dataclasses import dataclass
from ctypes import wintypes

import psutil


@dataclass
class MemoryStats:
    """Memory statistics in MB"""
    total: int
    active: int
    modified: int
    standby: int
    free: int


PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_SET_QUOTA = 0x0100
SYSTEM_MEMORY_LIST_INFORMATION = 80
SYSTEM_BASIC_INFORMATION = 0
SYSTEM_PERFORMANCE_INFORMATION = 2
MEMORY_EMPTY_WORKING_SETS = 2
MEMORY_FLUSH_MODIFIED_LIST = 3
MEMORY_PURGE_STANDBY_LIST = 4
MEMORY_PURGE_LOW_PRIORITY_STANDBY_LIST = 5
TOKEN_ADJUST_PRIVILEGES = 0x0020
TOKEN_QUERY = 0x0008
SE_PRIVILEGE_ENABLED = 0x00000002
STATUS_PRIVILEGE_NOT_HELD = 0xC0000061

# System information class constants
SystemBasicInformation = 0
SystemPerformanceInformation = 2
SystemMemoryListInformation = 80


kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
psapi = ctypes.WinDLL("psapi", use_last_error=True)
ntdll = ctypes.WinDLL("ntdll", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)
advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)


class PERFORMANCE_INFORMATION(ctypes.Structure):
    """Structure for GetPerformanceInfo Windows API."""
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("CommitTotal", ctypes.c_size_t),
        ("CommitLimit", ctypes.c_size_t),
        ("CommitPeak", ctypes.c_size_t),
        ("PhysicalTotal", ctypes.c_size_t),
        ("PhysicalAvailable", ctypes.c_size_t),
        ("SystemCache", ctypes.c_size_t),
        ("KernelTotal", ctypes.c_size_t),
        ("KernelPaged", ctypes.c_size_t),
        ("KernelNonpaged", ctypes.c_size_t),
        ("PageSize", ctypes.c_size_t),
        ("HandleCount", wintypes.DWORD),
        ("ProcessCount", wintypes.DWORD),
        ("ThreadCount", wintypes.DWORD),
    ]


class SYSTEM_BASIC_INFORMATION(ctypes.Structure):
    """Structure for SystemBasicInformation."""
    _fields_ = [
        ("Reserved", wintypes.DWORD),
        ("TimerResolution", wintypes.DWORD),
        ("PageSize", wintypes.DWORD),
        ("NumberOfPhysicalPages", wintypes.DWORD),
        ("LowestPhysicalPageNumber", wintypes.DWORD),
        ("HighestPhysicalPageNumber", wintypes.DWORD),
        ("AllocationGranularity", wintypes.DWORD),
        ("MinimumUserModeAddress", ctypes.c_void_p),
        ("MaximumUserModeAddress", ctypes.c_void_p),
        ("ActiveProcessorsAffinityMask", ctypes.c_void_p),
        ("NumberOfProcessors", ctypes.c_byte),
    ]


class SYSTEM_PERFORMANCE_INFORMATION(ctypes.Structure):
    """Structure for SystemPerformanceInformation - contains detailed memory stats."""
    _fields_ = [
        ("IdleProcessTime", ctypes.c_int64),
        ("IoReadTransferCount", ctypes.c_int64),
        ("IoWriteTransferCount", ctypes.c_int64),
        ("IoOtherTransferCount", ctypes.c_int64),
        ("IoReadOperationCount", wintypes.DWORD),
        ("IoWriteOperationCount", wintypes.DWORD),
        ("IoOtherOperationCount", wintypes.DWORD),
        ("AvailablePages", wintypes.DWORD),
        ("CommittedPages", wintypes.DWORD),
        ("CommitLimit", wintypes.DWORD),
        ("PeakCommitment", wintypes.DWORD),
        ("PageFaultCount", wintypes.DWORD),
        ("CopyOnWriteCount", wintypes.DWORD),
        ("TransitionCount", wintypes.DWORD),
        ("CacheTransitionCount", wintypes.DWORD),
        ("DemandZeroCount", wintypes.DWORD),
        ("PageReadCount", wintypes.DWORD),
        ("PageReadIoCount", wintypes.DWORD),
        ("CacheReadCount", wintypes.DWORD),
        ("CacheIoCount", wintypes.DWORD),
        ("DirtyPagesWriteCount", wintypes.DWORD),
        ("DirtyWriteIoCount", wintypes.DWORD),
        ("MappedPagesWriteCount", wintypes.DWORD),
        ("MappedWriteIoCount", wintypes.DWORD),
        ("PagedPoolPages", wintypes.DWORD),
        ("NonPagedPoolPages", wintypes.DWORD),
        ("PagedPoolAllocs", wintypes.DWORD),
        ("PagedPoolFrees", wintypes.DWORD),
        ("NonPagedPoolAllocs", wintypes.DWORD),
        ("NonPagedPoolFrees", wintypes.DWORD),
        ("FreeSystemPtes", wintypes.DWORD),
        ("ResidentSystemCodePage", wintypes.DWORD),
        ("TotalSystemDriverPages", wintypes.DWORD),
        ("TotalSystemCodePages", wintypes.DWORD),
        ("NonPagedPoolLookasideHits", wintypes.DWORD),
        ("PagedPoolLookasideHits", wintypes.DWORD),
        ("AvailablePagedPoolPages", wintypes.DWORD),
        ("ResidentSystemCachePage", wintypes.DWORD),
        ("ResidentPagedPoolPage", wintypes.DWORD),
        ("ResidentSystemDriverPage", wintypes.DWORD),
        ("CcFastReadNoWait", wintypes.DWORD),
        ("CcFastReadWait", wintypes.DWORD),
        ("CcFastReadResourceMiss", wintypes.DWORD),
        ("CcFastReadNotPossible", wintypes.DWORD),
        ("CcFastMdlReadNoWait", wintypes.DWORD),
        ("CcFastMdlReadWait", wintypes.DWORD),
        ("CcFastMdlReadResourceMiss", wintypes.DWORD),
        ("CcFastMdlReadNotPossible", wintypes.DWORD),
        ("CcMapDataNoWait", wintypes.DWORD),
        ("CcMapDataWait", wintypes.DWORD),
        ("CcMapDataNoWaitMiss", wintypes.DWORD),
        ("CcMapDataWaitMiss", wintypes.DWORD),
        ("CcPinMappedDataCount", wintypes.DWORD),
        ("CcPinReadNoWait", wintypes.DWORD),
        ("CcPinReadWait", wintypes.DWORD),
        ("CcPinReadNoWaitMiss", wintypes.DWORD),
        ("CcPinReadWaitMiss", wintypes.DWORD),
        ("CcCopyReadNoWait", wintypes.DWORD),
        ("CcCopyReadWait", wintypes.DWORD),
        ("CcCopyReadNoWaitMiss", wintypes.DWORD),
        ("CcCopyReadWaitMiss", wintypes.DWORD),
        ("CcMdlReadNoWait", wintypes.DWORD),
        ("CcMdlReadWait", wintypes.DWORD),
        ("CcMdlReadNoWaitMiss", wintypes.DWORD),
        ("CcMdlReadWaitMiss", wintypes.DWORD),
        ("CcReadAheadIos", wintypes.DWORD),
        ("CcLazyWriteIos", wintypes.DWORD),
        ("CcLazyWritePages", wintypes.DWORD),
        ("CcDataFlushes", wintypes.DWORD),
        ("CcDataPages", wintypes.DWORD),
        ("ContextSwitches", wintypes.DWORD),
        ("FirstLevelTbFills", wintypes.DWORD),
        ("SecondLevelTbFills", wintypes.DWORD),
        ("SystemCalls", wintypes.DWORD),
    ]


class SYSTEM_MEMORY_LIST_INFO_STRUCT(ctypes.Structure):
    """Structure for SystemMemoryListInformation - provides actual memory list counts.

    This structure gives accurate counts for each memory list type, including
    the modified page list, which is what RAMMap uses.
    """
    _fields_ = [
        ("ZeroPageCount", ctypes.c_size_t),
        ("FreePageCount", ctypes.c_size_t),
        ("ModifiedPageCount", ctypes.c_size_t),
        ("ModifiedNoWritePageCount", ctypes.c_size_t),
        ("BadPageCount", ctypes.c_size_t),
        ("PageCountByPriority", ctypes.c_size_t * 8),  # Standby list by priority (0-7)
        ("RepurposedPagesByPriority", ctypes.c_size_t * 8),
        ("ModifiedPageCountPageFile", ctypes.c_size_t),
    ]


class LUID(ctypes.Structure):
    _fields_ = [("LowPart", wintypes.DWORD), ("HighPart", wintypes.LONG)]


class LUID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Luid", LUID), ("Attributes", wintypes.DWORD)]


class TOKEN_PRIVILEGES(ctypes.Structure):
    _fields_ = [("PrivilegeCount", wintypes.DWORD), ("Privileges", LUID_AND_ATTRIBUTES * 1)]


@dataclass
class WorkingSetResult:
    success_count: int
    failed_count: int


def is_admin() -> bool:
    try:
        return bool(shell32.IsUserAnAdmin())
    except Exception:
        return False


def _open_process_token(access: int) -> wintypes.HANDLE | None:
    """Open current process token with specified access rights."""
    token = wintypes.HANDLE()
    current_process = ctypes.c_void_p(-1)
    if advapi32.OpenProcessToken(current_process, access, ctypes.byref(token)):
        return token
    return None


def check_privilege_status(privilege_name: str) -> tuple[str, str]:
    """Returns (status, error_detail) where status is 'enabled', 'available', 'missing', or 'error'."""
    token = _open_process_token(TOKEN_QUERY)
    if not token:
        return ("error", f"OpenProcessToken failed, last error: {ctypes.get_last_error()}")

    try:
        luid = LUID()
        if not advapi32.LookupPrivilegeValueW(None, privilege_name, ctypes.byref(luid)):
            return ("missing", f"LookupPrivilegeValueW failed, last error: {ctypes.get_last_error()}")

        # Check if privilege is in the token
        privileges_size = wintypes.DWORD()
        advapi32.GetTokenInformation(token, 3, None, 0, ctypes.byref(privileges_size))

        if privileges_size.value == 0:
            return ("error", "GetTokenInformation returned size 0")

        buffer = ctypes.create_string_buffer(privileges_size.value)
        if not advapi32.GetTokenInformation(
            token, 3, buffer, privileges_size.value, ctypes.byref(privileges_size)
        ):
            return ("error", f"GetTokenInformation failed, last error: {ctypes.get_last_error()}")

        # Parse TOKEN_PRIVILEGES structure - need dynamic array size
        class TOKEN_PRIVILEGES_DYNAMIC(ctypes.Structure):
            pass

        # Read privilege count first
        priv_count = ctypes.c_ulong.from_buffer(buffer, 0).value

        # Define structure with correct array size
        TOKEN_PRIVILEGES_DYNAMIC._fields_ = [
            ("PrivilegeCount", wintypes.DWORD),
            ("Privileges", LUID_AND_ATTRIBUTES * priv_count),
        ]

        token_privs = TOKEN_PRIVILEGES_DYNAMIC.from_buffer_copy(buffer)

        for i in range(token_privs.PrivilegeCount):
            priv = token_privs.Privileges[i]

            if priv.Luid.LowPart == luid.LowPart and priv.Luid.HighPart == luid.HighPart:
                if priv.Attributes & SE_PRIVILEGE_ENABLED:
                    return ("enabled", "")
                return ("available", "")

        return ("missing", f"Privilege not found in token (searched {token_privs.PrivilegeCount} privileges)")
    except Exception as e:
        return ("error", f"Exception: {type(e).__name__}: {e}")
    finally:
        kernel32.CloseHandle(token)


def _enable_privilege(privilege_name: str) -> bool:
    token = _open_process_token(TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY)
    if not token:
        return False

    try:
        luid = LUID()
        if not advapi32.LookupPrivilegeValueW(None, privilege_name, ctypes.byref(luid)):
            return False

        privileges = TOKEN_PRIVILEGES(
            PrivilegeCount=1,
            Privileges=(LUID_AND_ATTRIBUTES(luid, SE_PRIVILEGE_ENABLED),),
        )
        ctypes.set_last_error(0)
        if not advapi32.AdjustTokenPrivileges(
            token, False, ctypes.byref(privileges), 0, None, None
        ):
            return False

        # AdjustTokenPrivileges may return success while setting ERROR_NOT_ALL_ASSIGNED.
        return ctypes.get_last_error() == 0
    finally:
        kernel32.CloseHandle(token)


def _get_detailed_memory_info() -> tuple[int, int, int, int] | None:
    """
    Query detailed memory information using NtQuerySystemInformation.

    Returns: (total_pages, available_pages, modified_pages, standby_pages) or None if failed

    Requires SeProfileSingleProcessPrivilege to access detailed memory lists.
    Uses SYSTEM_MEMORY_LIST_INFORMATION to get accurate memory list counts.
    """
    # Try to enable the privilege (needed for detailed memory info)
    if not _enable_privilege("SeProfileSingleProcessPrivilege"):
        return None

    # Setup NtQuerySystemInformation function signature
    ntdll.NtQuerySystemInformation.argtypes = [
        ctypes.c_ulong,
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.POINTER(ctypes.c_ulong),
    ]
    ntdll.NtQuerySystemInformation.restype = ctypes.c_long

    # Get basic information for page size and total pages
    basic_info = SYSTEM_BASIC_INFORMATION()
    return_length = ctypes.c_ulong()
    status = ntdll.NtQuerySystemInformation(
        SystemBasicInformation,
        ctypes.byref(basic_info),
        ctypes.sizeof(basic_info),
        ctypes.byref(return_length),
    )

    if status != 0:
        return None

    page_size = basic_info.PageSize
    total_pages = basic_info.NumberOfPhysicalPages

    # Get performance information for available pages
    perf_info = SYSTEM_PERFORMANCE_INFORMATION()
    status = ntdll.NtQuerySystemInformation(
        SystemPerformanceInformation,
        ctypes.byref(perf_info),
        ctypes.sizeof(perf_info),
        ctypes.byref(return_length),
    )

    if status != 0:
        return None

    available_pages = perf_info.AvailablePages

    # Query SYSTEM_MEMORY_LIST_INFORMATION for accurate memory list counts
    # This is what RAMMap uses to get the real modified page count
    mem_list_info = SYSTEM_MEMORY_LIST_INFO_STRUCT()
    status = ntdll.NtQuerySystemInformation(
        SystemMemoryListInformation,
        ctypes.byref(mem_list_info),
        ctypes.sizeof(mem_list_info),
        ctypes.byref(return_length),
    )

    if status != 0:
        # If we can't get memory list info, fail gracefully
        return None

    # Extract accurate counts from SYSTEM_MEMORY_LIST_INFORMATION
    # Modified pages = ModifiedPageCount + ModifiedNoWritePageCount
    modified_pages = mem_list_info.ModifiedPageCount + mem_list_info.ModifiedNoWritePageCount

    # Standby pages = sum of all priority standby lists (0-7)
    standby_pages = sum(mem_list_info.PageCountByPriority[i] for i in range(8))

    return (total_pages, available_pages, modified_pages, standby_pages)


def _empty_working_set_for_pid(pid: int) -> bool:
    handle = kernel32.OpenProcess(
        PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_SET_QUOTA,
        False,
        pid,
    )
    if not handle:
        return False

    try:
        return bool(psapi.EmptyWorkingSet(handle))
    finally:
        kernel32.CloseHandle(handle)


def trim_all_working_sets() -> WorkingSetResult:
    success = failed = 0
    for process in psutil.process_iter(["pid"]):
        pid = process.info.get("pid")
        if not pid or pid in (0, 4):
            continue
        if _empty_working_set_for_pid(pid):
            success += 1
        else:
            failed += 1
    return WorkingSetResult(success_count=success, failed_count=failed)


def purge_standby_list() -> int:
    if not _enable_privilege("SeProfileSingleProcessPrivilege"):
        return STATUS_PRIVILEGE_NOT_HELD

    ntdll.NtSetSystemInformation.argtypes = [
        ctypes.c_ulong,
        ctypes.c_void_p,
        ctypes.c_ulong,
    ]
    ntdll.NtSetSystemInformation.restype = ctypes.c_long

    command = ctypes.c_ulong(MEMORY_PURGE_STANDBY_LIST)
    status = ntdll.NtSetSystemInformation(
        SYSTEM_MEMORY_LIST_INFORMATION,
        ctypes.byref(command),
        ctypes.sizeof(command),
    )
    return int(status)


def purge_modified_list() -> int:
    if not _enable_privilege("SeProfileSingleProcessPrivilege"):
        return STATUS_PRIVILEGE_NOT_HELD

    ntdll.NtSetSystemInformation.argtypes = [
        ctypes.c_ulong,
        ctypes.c_void_p,
        ctypes.c_ulong,
    ]
    ntdll.NtSetSystemInformation.restype = ctypes.c_long

    command = ctypes.c_ulong(MEMORY_FLUSH_MODIFIED_LIST)
    status = ntdll.NtSetSystemInformation(
        SYSTEM_MEMORY_LIST_INFORMATION,
        ctypes.byref(command),
        ctypes.sizeof(command),
    )
    return int(status)


def get_memory_stats() -> MemoryStats:
    """Get detailed memory statistics using Windows NtQuerySystemInformation API.

    Returns memory stats in MB.

    Memory breakdown on Windows:
    - Total = Active + Modified + Standby + Free (+ Zero, included in Free)
    - Active: In-use memory (working sets of processes)
    - Modified: Changed pages not yet written to disk (requires admin privileges)
    - Standby: Cached memory ready to be repurposed (requires admin privileges)
    - Free: Available memory (including zero page list)

    This function uses SYSTEM_MEMORY_LIST_INFORMATION for accurate memory stats.
    Requires Administrator privileges with SeProfileSingleProcessPrivilege.

    If accurate data cannot be obtained (no admin privileges), returns basic stats
    with modified=0 and standby=0 to indicate data is unavailable.
    """
    # Try to get detailed memory information using SYSTEM_MEMORY_LIST_INFORMATION
    detailed_info = _get_detailed_memory_info()

    if detailed_info:
        total_pages, available_pages, modified_pages, standby_pages = detailed_info

        # Get page size from basic info
        basic_info = SYSTEM_BASIC_INFORMATION()
        return_length = ctypes.c_ulong()
        status = ntdll.NtQuerySystemInformation(
            SystemBasicInformation,
            ctypes.byref(basic_info),
            ctypes.sizeof(basic_info),
            ctypes.byref(return_length),
        )

        if status == 0:
            page_size = basic_info.PageSize

            def pages_to_mb(pages):
                return (pages * page_size) // (1024 * 1024)

            total_mb = pages_to_mb(total_pages)
            available_mb = pages_to_mb(available_pages)
            standby_mb = pages_to_mb(standby_pages)
            modified_mb = pages_to_mb(modified_pages)

            # In-use = Total - Available = Active + Modified
            in_use_mb = total_mb - available_mb
            active_mb = max(0, in_use_mb - modified_mb)

            # Free = Available - Standby
            free_mb = max(0, available_mb - standby_mb)

            # Validate and adjust
            calculated_total = active_mb + modified_mb + standby_mb + free_mb
            if calculated_total != total_mb:
                diff = total_mb - calculated_total
                free_mb = max(0, free_mb + diff)

            return MemoryStats(
                total=total_mb,
                active=active_mb,
                modified=modified_mb,
                standby=standby_mb,
                free=free_mb
            )

    # Could not get accurate data from SYSTEM_MEMORY_LIST_INFORMATION
    # Return basic stats without modified/standby details
    # Modified and Standby will be shown as 0 (data unavailable - need admin)

    mem = psutil.virtual_memory()
    bytes_to_mb = 1024 * 1024

    total_mb = mem.total // bytes_to_mb
    available_mb = mem.available // bytes_to_mb
    used_mb = mem.used // bytes_to_mb

    # Basic breakdown: Total = Used + Available
    # Without kernel access, we can't split Used into Active+Modified
    # or Available into Standby+Free
    # So we report: Active (used), Modified=0, Standby=0, Free (available)

    return MemoryStats(
        total=total_mb,
        active=used_mb,
        modified=0,  # Unavailable without admin privileges
        standby=0,   # Unavailable without admin privileges
        free=available_mb
    )
