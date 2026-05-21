from unittest.mock import MagicMock, patch

import pytest

from utils.safe_executor import CommandStatus, CommandResult, CommandTask


class TestCommandResult:

    def test_success_result(self):
        result = CommandResult(
            status=CommandStatus.SUCCESS,
            return_code=0,
            stdout="ok",
            stderr="",
        )
        assert result.status == CommandStatus.SUCCESS
        assert result.return_code == 0
        assert result.stdout == "ok"
        assert result.error_message is None

    def test_failed_result_with_error(self):
        result = CommandResult(
            status=CommandStatus.FAILED,
            return_code=1,
            stdout="",
            stderr="error",
            error_message="something failed",
        )
        assert result.status == CommandStatus.FAILED
        assert result.error_message == "something failed"


class TestCommandStatus:

    def test_status_values(self):
        assert CommandStatus.PENDING.value == "pending"
        assert CommandStatus.RUNNING.value == "running"
        assert CommandStatus.SUCCESS.value == "success"
        assert CommandStatus.FAILED.value == "failed"
        assert CommandStatus.CANCELLED.value == "cancelled"


class TestCommandTaskCancel:

    def test_cancel_sets_flag(self):
        task = CommandTask("echo hello")
        assert not task._is_cancelled
        task.cancel()
        assert task._is_cancelled

    def test_cancelled_task_returns_cancelled_result(self):
        task = CommandTask("echo hello")
        task.cancel()
        with patch.object(task, "callback", None):
            task.run()
        assert task._is_cancelled


class TestCommandTaskExecute:

    def test_successful_command(self):
        task = CommandTask("echo hello")
        result = task._execute_command()
        assert result.status == CommandStatus.SUCCESS
        assert result.return_code == 0
        assert "hello" in result.stdout

    def test_failed_command(self):
        task = CommandTask("nonexistent_command_12345")
        result = task._execute_command()
        assert result.status == CommandStatus.FAILED

    def test_command_with_callback(self):
        callback = MagicMock()
        task = CommandTask("echo test", callback=callback)
        with patch("utils.safe_executor.QTimer") as mock_timer:
            mock_timer.singleShot = MagicMock()
            task.run()
            assert mock_timer.singleShot.called

    def test_permission_error_handling(self):
        task = CommandTask("echo hello")
        with patch("subprocess.Popen", side_effect=PermissionError("denied")):
            result = task._execute_command()
            assert result.status == CommandStatus.FAILED
            assert "权限不足" in result.error_message

    def test_file_not_found_error_handling(self):
        task = CommandTask("echo hello")
        with patch("subprocess.Popen", side_effect=FileNotFoundError("not found")):
            result = task._execute_command()
            assert result.status == CommandStatus.FAILED
            assert "不存在" in result.error_message

    def test_generic_exception_handling(self):
        task = CommandTask("echo hello")
        with patch("subprocess.Popen", side_effect=RuntimeError("boom")):
            result = task._execute_command()
            assert result.status == CommandStatus.FAILED
            assert "执行失败" in result.error_message
