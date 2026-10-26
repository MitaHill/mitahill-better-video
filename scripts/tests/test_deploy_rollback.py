import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        (self.root / ".env").touch()
        (self.root / "docker-compose.yaml").write_text("services: {}\n")
        self.script = Path(__file__).resolve().parents[1] / "loop" / "remote-run.sh"
        # CI 将 tests 挂载到 /workspace/tests，部署脚本随同测试单独挂载。
        if not self.script.exists():
            self.script = Path("/workspace/scripts/loop/remote-run.sh")
        self.assertTrue(self.script.is_file(), "部署脚本必须随测试提供")
        self.executable("flock", "#!/bin/sh\nexit 0\n")
        self.executable("sleep", "#!/bin/sh\nexit 0\n")
        self.executable("curl", '''#!/usr/bin/env python3
import json, os, pathlib, sys
root = pathlib.Path(os.environ["DEPLOY_TEST_ROOT"])
override = root / ".deploy-image.yml"
rollback = override.exists() and "rollback-" in override.read_text()
scenario = os.environ["SCENARIO"]
if scenario == "health_failure" and not rollback or scenario == "rollback_failure":
    sys.exit(1)
print(json.dumps({"status": "ok", "db": "ok", "worker": "running"}))
''')
        self.executable("docker", '''#!/usr/bin/env python3
import os, pathlib, sys
root = pathlib.Path(os.environ["DEPLOY_TEST_ROOT"])
args = sys.argv[1:]
with (root / "calls").open("a") as f:
    f.write(" ".join(args) + "\\n")
scenario = os.environ["SCENARIO"]
if args[0] == "inspect":
    print("sha256:old")
elif args[0] == "exec":
    sys.exit(1 if scenario == "busy" else 0)
elif args[0] == "pull":
    sys.exit(1 if scenario == "pull_failure" else 0)
elif args[:2] == ["image", "inspect"]:
    print("kindmitaishere/mitahill-better-video@sha256:new" if "RepoDigests" in args[-1] else "sha256:new")
elif args[0] == "compose" and "up" in args:
    override = (root / ".deploy-image.yml").read_text()
    rollback = "rollback-" in override
    if scenario == "start_failure" and not rollback or scenario == "rollback_failure" and rollback:
        sys.exit(1)
''')

    def executable(self, name, source):
        path = self.bin / name
        path.write_text(source)
        path.chmod(0o755)

    def run_deploy(self, scenario):
        env = dict(os.environ, PATH=f"{self.bin}{os.pathsep}{os.environ['PATH']}",
                   DEPLOY_TEST_ROOT=str(self.root), SCENARIO=scenario, HEALTH_TIMEOUT_SECONDS="1")
        result = subprocess.run(["bash", str(self.script)], cwd=self.root, env=env, capture_output=True, text=True, timeout=15)
        return result, (self.root / "calls").read_text()

    def test_success_pins_digest_and_keeps_old_image(self):
        result, calls = self.run_deploy("success")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("@sha256:new", (self.root / ".deploy-image.yml").read_text())
        self.assertTrue((self.root / ".deploy-rollback-image").is_file())
        self.assertLess(calls.index("pull "), calls.index("up -d"))
        self.assertNotIn("down", calls)
        self.assertNotIn("rmi", calls)

    def test_pull_failure_keeps_running_service(self):
        result, calls = self.run_deploy("pull_failure")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("up -d", calls)
        self.assertFalse((self.root / ".deploy-image.yml").exists())

    def test_busy_service_is_not_restarted(self):
        result, calls = self.run_deploy("busy")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("pull ", calls)
        self.assertNotIn("up -d", calls)

    def test_start_failure_rolls_back_and_reports_failure(self):
        result, calls = self.run_deploy("start_failure")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(calls.count("up -d"), 2)
        self.assertIn("已恢复上一版本", result.stderr)

    def test_health_failure_rolls_back(self):
        result, calls = self.run_deploy("health_failure")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(calls.count("up -d"), 2)
        self.assertIn("rollback-", (self.root / ".deploy-image.yml").read_text())
        self.assertIn("已恢复上一版本", result.stderr)

    def test_rollback_failure_is_explicit(self):
        result, _ = self.run_deploy("rollback_failure")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("回滚失败，需要人工处理", result.stderr)


if __name__ == "__main__":
    unittest.main()
