import os
import shutil

from PyQt6.QtWidgets import QMessageBox

from utils.path_resolver import PathResolver
from utils.safe_executor import CommandResult, CommandStatus


class WorkspaceActionExecutor:
    """工作台命令动作执行器：负责命令预览、执行和压缩兜底。"""

    def __init__(self, parent, command_manager, executor):
        self.parent = parent
        self.command_manager = command_manager
        self.executor = executor

    def populate_presets(self, cmb_preset) -> None:
        cmb_preset.clear()
        cmb_preset.addItem("选择命令模板...")
        for template in self.command_manager.get_all_templates():
            cmb_preset.addItem(template.name, template.template_id)

    def update_command_preview(
        self,
        selected_entry: dict,
        selected_scope,
        cmb_preset,
        cmd_preview,
        btn_execute,
    ) -> None:
        if not selected_entry:
            cmd_preview.clear()
            btn_execute.setEnabled(False)
            return

        image_path = selected_entry.get("image_path", "")
        preset_id = cmb_preset.currentData()
        if not preset_id:
            cmd_preview.clear()
            btn_execute.setEnabled(False)
            return

        target = PathResolver.resolve(image_path, selected_scope)
        if not target:
            cmd_preview.clear()
            btn_execute.setEnabled(False)
            return

        if preset_id == "encrypt_compress":
            output_path = self._generate_output_path(target)
            command = self.command_manager.apply_template(
                preset_id,
                input=target,
                output=output_path,
                password="1",
            )
        else:
            command = self.command_manager.apply_template(preset_id, target=target)

        if not command:
            cmd_preview.clear()
            btn_execute.setEnabled(False)
            return

        cmd_preview.setText(command)
        btn_execute.setEnabled(True)

    def execute_command(
        self,
        selected_entry: dict,
        selected_scope,
        cmb_preset,
        cmd_preview,
    ) -> None:
        command = cmd_preview.toPlainText()
        if not command:
            return

        preset_id = cmb_preset.currentData()
        if preset_id == "encrypt_compress":
            self._execute_encrypt_compress(
                selected_entry=selected_entry,
                selected_scope=selected_scope,
                preset_id=preset_id,
            )
            return

        self.executor.execute(command, self._build_callback())

    def _execute_encrypt_compress(self, selected_entry: dict, selected_scope, preset_id: str) -> None:
        image_path = selected_entry.get("image_path", "")
        target = PathResolver.resolve(image_path, selected_scope)
        if not target:
            QMessageBox.warning(self.parent, "错误", "目标路径无效，无法执行加密压缩")
            return

        default_output = self._generate_output_path(target)
        output_path = PathResolver.save_file(
            self.parent,
            "选择压缩文件保存位置",
            os.path.basename(default_output),
            "ZIP 文件 (*.zip)",
        )
        if not output_path:
            return

        if self._check_7z_available():
            command = self.command_manager.apply_template(
                preset_id,
                input=target,
                output=output_path,
                password="1",
            )
            if not command:
                QMessageBox.warning(self.parent, "错误", "生成压缩命令失败")
                return
            self.executor.execute(command, self._build_callback())
            return

        self._compress_with_pyzipper(target, output_path, "1")

    def _build_callback(self):
        def callback(result: CommandResult):
            if result.status == CommandStatus.SUCCESS:
                QMessageBox.information(self.parent, "成功", "命令执行成功")
                return
            error_msg = result.error_message or result.stderr
            full_msg = f"命令执行失败\n\n错误信息:\n{error_msg}\n\n返回码: {result.return_code}"
            QMessageBox.warning(self.parent, "执行失败", full_msg)

        return callback

    def _generate_output_path(self, input_path: str) -> str:
        if os.path.isfile(input_path):
            base = os.path.splitext(input_path)[0]
            return f"{base}.zip"
        dir_name = os.path.basename(input_path.rstrip(os.sep))
        return os.path.join(os.path.dirname(input_path), f"{dir_name}.zip")

    def _check_7z_available(self) -> bool:
        try:
            return shutil.which("7z") is not None
        except Exception:
            return False

    def _compress_with_pyzipper(self, input_path: str, output_path: str, password: str) -> None:
        try:
            import pyzipper

            with pyzipper.AESZipFile(
                output_path,
                "w",
                compression=pyzipper.ZIP_DEFLATED,
                encryption=pyzipper.WZ_AES,
            ) as zipf:
                zipf.setpassword(password.encode("utf-8"))

                if os.path.isfile(input_path):
                    filename = os.path.basename(input_path)
                    zipf.write(input_path, filename)
                elif os.path.isdir(input_path):
                    for root, _, files in os.walk(input_path):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, os.path.dirname(input_path))
                            zipf.write(file_path, arcname)

            QMessageBox.information(
                self.parent,
                "成功",
                f"文件已加密压缩并保存到：\n{output_path}\n\n密码: {password}",
            )
        except ImportError:
            QMessageBox.critical(self.parent, "错误", "pyzipper 库未安装\n\n请运行: pip install pyzipper")
        except PermissionError as exc:
            QMessageBox.critical(self.parent, "错误", f"权限不足: {exc}")
        except Exception as exc:
            QMessageBox.critical(self.parent, "错误", f"压缩失败: {exc}")
