from __future__ import annotations

import ctypes
import os
from ctypes import wintypes

_JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
_PROCESS_TERMINATE = 0x0001
_PROCESS_SET_QUOTA = 0x0100


class _IoCounters(ctypes.Structure):
	_fields_ = [
		("read_operation_count", ctypes.c_ulonglong),
		("write_operation_count", ctypes.c_ulonglong),
		("other_operation_count", ctypes.c_ulonglong),
		("read_transfer_count", ctypes.c_ulonglong),
		("write_transfer_count", ctypes.c_ulonglong),
		("other_transfer_count", ctypes.c_ulonglong),
	]


class _JobObjectBasicLimitInformation(ctypes.Structure):
	_fields_ = [
		("per_process_user_time_limit", ctypes.c_longlong),
		("per_job_user_time_limit", ctypes.c_longlong),
		("limit_flags", wintypes.DWORD),
		("minimum_working_set_size", ctypes.c_size_t),
		("maximum_working_set_size", ctypes.c_size_t),
		("active_process_limit", wintypes.DWORD),
		("affinity", ctypes.c_size_t),
		("priority_class", wintypes.DWORD),
		("scheduling_class", wintypes.DWORD),
	]


class _JobObjectExtendedLimitInformation(ctypes.Structure):
	_fields_ = [
		("basic_limit_information", _JobObjectBasicLimitInformation),
		("io_info", _IoCounters),
		("process_memory_limit", ctypes.c_size_t),
		("job_memory_limit", ctypes.c_size_t),
		("peak_process_memory_used", ctypes.c_size_t),
		("peak_job_memory_used", ctypes.c_size_t),
	]


class KillOnCloseJob:
	"""Own a Windows process tree whose members die when this process loses the job handle."""

	def __init__(self) -> None:
		self._handle: int | None = None
		if os.name != "nt":
			return
		kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
		kernel32.CreateJobObjectW.argtypes = (ctypes.c_void_p, wintypes.LPCWSTR)
		kernel32.CreateJobObjectW.restype = wintypes.HANDLE
		kernel32.SetInformationJobObject.argtypes = (
			wintypes.HANDLE,
			ctypes.c_int,
			ctypes.c_void_p,
			wintypes.DWORD,
		)
		kernel32.SetInformationJobObject.restype = wintypes.BOOL
		handle = kernel32.CreateJobObjectW(None, None)
		if not handle:
			raise ctypes.WinError(ctypes.get_last_error())
		information = _JobObjectExtendedLimitInformation()
		information.basic_limit_information.limit_flags = _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
		if not kernel32.SetInformationJobObject(
			handle,
			_JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
			ctypes.byref(information),
			ctypes.sizeof(information),
		):
			error = ctypes.WinError(ctypes.get_last_error())
			kernel32.CloseHandle(handle)
			raise error
		self._handle = int(handle)

	def assign(self, process_id: int) -> None:
		if self._handle is None:
			return
		kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
		kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
		kernel32.OpenProcess.restype = wintypes.HANDLE
		kernel32.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
		kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
		kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
		kernel32.CloseHandle.restype = wintypes.BOOL
		process_handle = kernel32.OpenProcess(_PROCESS_TERMINATE | _PROCESS_SET_QUOTA, False, process_id)
		if not process_handle:
			raise ctypes.WinError(ctypes.get_last_error())
		try:
			if not kernel32.AssignProcessToJobObject(self._handle, process_handle):
				raise ctypes.WinError(ctypes.get_last_error())
		finally:
			kernel32.CloseHandle(process_handle)

	def close(self) -> None:
		if self._handle is None:
			return
		kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
		kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
		kernel32.CloseHandle.restype = wintypes.BOOL
		kernel32.CloseHandle(self._handle)
		self._handle = None

	def peak_memory_bytes(self) -> int | None:
		"""Return peak memory charged to the owned Windows process tree."""

		if self._handle is None:
			return None
		kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
		kernel32.QueryInformationJobObject.argtypes = (
			wintypes.HANDLE,
			ctypes.c_int,
			ctypes.c_void_p,
			wintypes.DWORD,
			ctypes.POINTER(wintypes.DWORD),
		)
		kernel32.QueryInformationJobObject.restype = wintypes.BOOL
		information = _JobObjectExtendedLimitInformation()
		if not kernel32.QueryInformationJobObject(
			self._handle,
			_JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
			ctypes.byref(information),
			ctypes.sizeof(information),
			None,
		):
			raise ctypes.WinError(ctypes.get_last_error())
		return int(information.peak_job_memory_used)

	def __del__(self) -> None:
		self.close()
