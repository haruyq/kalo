"""Read-only external access to a Unity Mono process (no injection, no writes)."""
import ctypes
import ctypes.wintypes as wt
import struct

k32 = ctypes.WinDLL('kernel32', use_last_error=True)
psapi = ctypes.WinDLL('psapi', use_last_error=True)
k32.OpenProcess.restype = wt.HANDLE
k32.ReadProcessMemory.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
psapi.EnumProcessModulesEx.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.DWORD, ctypes.POINTER(wt.DWORD), wt.DWORD]
psapi.GetModuleBaseNameW.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.LPWSTR, wt.DWORD]
psapi.GetModuleFileNameExW.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.LPWSTR, wt.DWORD]

PROCESS_QUERY_INFORMATION, PROCESS_VM_READ = 0x0400, 0x0010


def find_pid(exe):
    arr = (wt.DWORD * 4096)()
    got = wt.DWORD()
    psapi.EnumProcesses(arr, ctypes.sizeof(arr), ctypes.byref(got))
    for pid in arr[:got.value // 4]:
        h = k32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
        if not h:
            continue
        buf = ctypes.create_unicode_buffer(260)
        ok = psapi.GetModuleBaseNameW(h, None, buf, 260)
        k32.CloseHandle(h)
        if ok and buf.value.lower() == exe.lower():
            return pid
    return None


class Proc:
    def __init__(self, exe):
        self.pid = find_pid(exe)
        if not self.pid:
            raise RuntimeError(f'{exe} is not running')
        self.h = k32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, self.pid)
        if not self.h:
            raise ctypes.WinError(ctypes.get_last_error())

    def read(self, addr, n):
        buf = ctypes.create_string_buffer(n)
        got = ctypes.c_size_t()
        if not addr or not k32.ReadProcessMemory(self.h, ctypes.c_void_p(addr), buf, n, ctypes.byref(got)):
            raise MemoryError(f'read failed at {addr:#x}')
        return buf.raw

    def try_read(self, addr, n):
        try:
            return self.read(addr, n)
        except MemoryError:
            return None

    def u8(self, a): return self.read(a, 1)[0]
    def u16(self, a): return struct.unpack('<H', self.read(a, 2))[0]
    def i32(self, a): return struct.unpack('<i', self.read(a, 4))[0]
    def u32(self, a): return struct.unpack('<I', self.read(a, 4))[0]
    def i64(self, a): return struct.unpack('<q', self.read(a, 8))[0]
    def ptr(self, a): return struct.unpack('<Q', self.read(a, 8))[0]
    def f32(self, a): return struct.unpack('<f', self.read(a, 4))[0]
    def f64(self, a): return struct.unpack('<d', self.read(a, 8))[0]

    def cstr(self, a, n=256):
        b = self.try_read(a, n)
        return b.split(b'\0', 1)[0].decode('utf-8', 'replace') if b else None

    def exe_path(self):
        buf = ctypes.create_unicode_buffer(1024)
        psapi.GetModuleFileNameExW(self.h, None, buf, 1024)
        return buf.value

    def module(self, name):
        mods = (ctypes.c_void_p * 1024)()
        got = wt.DWORD()
        psapi.EnumProcessModulesEx(self.h, mods, ctypes.sizeof(mods), ctypes.byref(got), 3)
        for m in mods[:got.value // 8]:
            buf = ctypes.create_unicode_buffer(260)
            psapi.GetModuleBaseNameW(self.h, m, buf, 260)
            if buf.value.lower() == name.lower():
                return m
        raise RuntimeError(f'module {name} not found')

    def export(self, base, name):
        pe = base + self.u32(base + 0x3C)
        exp = base + self.u32(pe + 0x18 + 0x70)  # PE32+ export data directory
        n, fns, names, ords = struct.unpack('<IIII', self.read(exp + 0x18, 16))
        for i in range(n):
            if self.cstr(base + self.u32(base + names + i * 4)) == name:
                return base + self.u32(base + fns + self.u16(base + ords + i * 2) * 4)
        raise RuntimeError(f'export {name} not found')


def mono_root_domain(p):
    base = p.module('mono-2.0-bdwgc.dll')
    fn = p.export(base, 'mono_get_root_domain')
    code = p.read(fn, 8)
    if code[:3] != b'\x48\x8b\x05' or code[7] != 0xC3:  # mov rax,[rip+disp32]; ret
        raise RuntimeError(f'unexpected mono_get_root_domain code: {code.hex()}')
    return p.ptr(fn + 7 + struct.unpack('<i', code[3:7])[0])


# Offsets probed on Unity 6000.0.66 MonoBleedingEdge x64 (KALPA 2026-10).
DOMAIN_ASSEMBLIES = 0xA0
ASSEMBLY_NAME, ASSEMBLY_IMAGE = 0x10, 0x60
IMAGE_CLASS_CACHE = 0x4D0          # MonoInternalHashTable: size @+0x18, table @+0x20
CLASS_PARENT, CLASS_NAME, CLASS_NS = 0x30, 0x48, 0x50
CLASS_VTABLE_SIZE, CLASS_FIELDS, CLASS_RUNTIME_INFO = 0x5C, 0x98, 0xD0
CLASS_FIELD_COUNT, CLASS_NEXT_CACHE, CLASS_GENERIC = 0x100, 0x108, 0xF0
FIELD_SIZE, VTABLE_METHODS = 0x20, 0x48
ARRAY_LEN, ARRAY_DATA = 0x18, 0x20


class Mono:
    def __init__(self, p, assembly='Assembly-CSharp'):
        self.p = p
        node = p.ptr(mono_root_domain(p) + DOMAIN_ASSEMBLIES)
        while node:
            a = p.ptr(node)
            if p.cstr(p.ptr(a + ASSEMBLY_NAME)) == assembly:
                break
            node = p.ptr(node + 8)
        else:
            raise RuntimeError(f'assembly {assembly} not loaded')
        img = p.ptr(a + ASSEMBLY_IMAGE)
        size, table = p.i32(img + IMAGE_CLASS_CACHE + 0x18), p.ptr(img + IMAGE_CLASS_CACHE + 0x20)
        self.classes = {}
        for i in range(size):
            c = p.ptr(table + i * 8)
            while c:
                self.classes[f'{p.cstr(p.ptr(c + CLASS_NS))}.{p.cstr(p.ptr(c + CLASS_NAME))}'.lstrip('.')] = c
                c = p.ptr(c + CLASS_NEXT_CACHE)
        self._fields = {}

    def name(self, c):
        return self.p.cstr(self.p.ptr(c + CLASS_NAME))

    def generic_def(self, c):
        """Container class if c is a generic instance, else None."""
        g = self.p.try_read(c + CLASS_GENERIC, 8)
        if not g:
            return None
        cc = self.p.try_read(struct.unpack('<Q', g)[0], 8)
        cc = cc and struct.unpack('<Q', cc)[0]
        if cc and cc != c and self.p.try_read(cc + CLASS_NAME, 8) and self.name(cc) == self.name(c):
            return cc
        return None

    def fields(self, c):
        """{name: (offset, is_static)} including inherited fields."""
        if c in self._fields:
            return self._fields[c]
        p, out, k = self.p, {}, c
        while k:
            d = self.generic_def(k)
            arr = p.ptr(k + CLASS_FIELDS) or (d and p.ptr(d + CLASS_FIELDS))
            n = p.i32((d or k) + CLASS_FIELD_COUNT)
            for i in range(n if arr else 0):
                f = arr + i * FIELD_SIZE
                nm = p.cstr(p.ptr(f + 8))
                out.setdefault(nm, (p.i32(f + 0x18), bool(p.u16(p.ptr(f) + 8) & 0x10)))
            k = p.ptr(k + CLASS_PARENT)
        self._fields[c] = out
        return out

    def static_data(self, c):
        vt = self.p.ptr(self.p.ptr(c + CLASS_RUNTIME_INFO) + 8)  # domain_vtables[0]
        return self.p.ptr(vt + VTABLE_METHODS + self.p.i32(c + CLASS_VTABLE_SIZE) * 8)

    def klass(self, obj):
        return self.p.ptr(self.p.ptr(obj))

    def off(self, c, field):
        fs = self.fields(c)
        hit = fs.get(field) or fs.get(f'<{field}>k__BackingField')  # auto-property
        if not hit:
            raise KeyError(f'{self.name(c)} has no field {field}')
        return hit[0]

    def static(self, cls_name, field):
        """Address of a static field."""
        c = self.classes[cls_name]
        return self.static_data(c) + self.off(c, field)

    def f(self, obj, field):
        """Address of an instance field (resolved via the object's runtime class)."""
        return obj + self.off(self.klass(obj), field)

    def walk(self, obj, *path):
        """Follow reference fields; returns 0 if any link is null."""
        for name in path:
            if not obj:
                return 0
            obj = self.p.ptr(self.f(obj, name))
        return obj

    def string(self, s):
        if not s:
            return None
        n = self.p.i32(s + 0x10)
        return self.p.read(s + 0x14, n * 2).decode('utf-16-le') if n else ''

    def array(self, arr):
        """(count, data address) of a managed array."""
        return (self.p.i32(arr + ARRAY_LEN), arr + ARRAY_DATA) if arr else (0, 0)

    def list_items(self, lst):
        """Element pointers of a List<T> of reference types."""
        if not lst:
            return []
        size = self.p.i32(self.f(lst, '_size'))
        _, data = self.array(self.p.ptr(self.f(lst, '_items')))
        return [self.p.ptr(data + i * 8) for i in range(size)]
