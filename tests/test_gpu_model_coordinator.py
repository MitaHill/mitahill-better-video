import importlib.util
import sys
import types
import unittest
from pathlib import Path


class FakeCuda:
    def __init__(self, allocated=0, reserved=0, available=True):
        self.allocated = allocated
        self.reserved = reserved
        self.available = available

    def is_available(self):
        return self.available

    def memory_allocated(self):
        return self.allocated

    def memory_reserved(self):
        return self.reserved

    def mem_get_info(self):
        return 6 * 1024**3, 8 * 1024**3

    def empty_cache(self):
        return None


class GpuModelCoordinatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original_torch = sys.modules.get("torch")
        cls.fake_cuda = FakeCuda()
        sys.modules["torch"] = types.SimpleNamespace(cuda=cls.fake_cuda)
        module_path = Path(__file__).parents[1] / "app/src/Worker/gpu_model_coordinator.py"
        spec = importlib.util.spec_from_file_location("gpu_model_coordinator_test", module_path)
        cls.coordinator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.coordinator)

    @classmethod
    def tearDownClass(cls):
        if cls.original_torch is None:
            sys.modules.pop("torch", None)
        else:
            sys.modules["torch"] = cls.original_torch

    def test_does_not_restart_without_cuda(self):
        self.fake_cuda.available = False
        restarted = []

        result = self.coordinator.restart_worker_if_cuda_memory_leaked(
            lambda: restarted.append(True)
        )

        self.assertFalse(result)
        self.assertEqual(restarted, [])

    def test_does_not_restart_for_other_gpu_users(self):
        self.fake_cuda.available = True
        self.fake_cuda.allocated = 0
        self.fake_cuda.reserved = 0
        restarted = []

        result = self.coordinator.restart_worker_if_cuda_memory_leaked(
            lambda: restarted.append(True)
        )

        self.assertFalse(result)
        self.assertEqual(restarted, [])

    def test_restarts_when_worker_cache_remains_large(self):
        self.fake_cuda.available = True
        self.fake_cuda.allocated = 0
        self.fake_cuda.reserved = 129 * 1024 * 1024
        restarted = []

        result = self.coordinator.restart_worker_if_cuda_memory_leaked(
            lambda: restarted.append(True)
        )

        self.assertTrue(result)
        self.assertEqual(restarted, [True])


if __name__ == "__main__":
    unittest.main()
