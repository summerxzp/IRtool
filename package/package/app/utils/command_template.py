from typing import Dict, Any, Optional
import re


class CommandTemplate:
    """命令模板类 - 支持参数替换"""
    
    def __init__(self, template_id: str, name: str, command: str, 
                 description: str = "", parameters: Optional[Dict[str, Any]] = None):
        """
        初始化命令模板
        
        Args:
            template_id: 模板ID
            name: 模板名称
            command: 命令模板（支持 {param} 占位符）
            description: 描述
            parameters: 参数定义
        """
        self.template_id = template_id
        self.name = name
        self.command = command
        self.description = description
        self.parameters = parameters or {}
    
    def apply(self, **kwargs) -> str:
        """
        应用参数到命令模板
        
        Args:
            **kwargs: 参数键值对
            
        Returns:
            替换后的命令字符串
        """
        command = self.command
        
        for key, value in kwargs.items():
            placeholder = f"{{{key}}}"
            command = command.replace(placeholder, str(value))
        
        return command
    
    def validate_parameters(self, **kwargs) -> bool:
        """
        验证参数是否完整
        
        Args:
            **kwargs: 参数键值对
            
        Returns:
            参数是否完整
        """
        for param in self.parameters.keys():
            if param not in kwargs:
                return False
        return True
    
    def get_required_parameters(self) -> list:
        """
        获取必需参数列表
        
        Returns:
            参数名称列表
        """
        return list(self.parameters.keys())


class CommandTemplateManager:
    """命令模板管理器"""
    
    def __init__(self):
        self.templates: Dict[str, CommandTemplate] = {}
        self._load_default_templates()
    
    def _load_default_templates(self):
        """加载默认模板"""
        self.templates = {
            "unlock_file": CommandTemplate(
                template_id="unlock_file",
                name="解锁文件",
                command='attrib -h -s -r "{target}" /s /d',
                description="移除文件的隐藏、系统、只读属性",
                parameters={"target": "目标路径"}
            ),
            "take_ownership": CommandTemplate(
                template_id="take_ownership",
                name="获取所有权",
                command='takeown /f "{target}" /r /d y',
                description="获取文件或目录的所有权",
                parameters={"target": "目标路径"}
            ),
            "delete_file": CommandTemplate(
                template_id="delete_file",
                name="删除文件",
                command='del /f /q "{target}"',
                description="强制删除文件",
                parameters={"target": "目标路径"}
            ),
            "encrypt_compress": CommandTemplate(
                template_id="encrypt_compress",
                name="加密压缩",
                command='7z a -tzip -p{password} -mem=AES256 -mx=9 -y "{output}" "{input}"',
                description="使用 7z 加密压缩文件/目录",
                parameters={
                    "input": "输入路径",
                    "output": "输出路径",
                    "password": "密码"
                }
            )
        }
    
    def add_template(self, template: CommandTemplate):
        """
        添加命令模板
        
        Args:
            template: 命令模板
        """
        self.templates[template.template_id] = template
    
    def get_template(self, template_id: str) -> Optional[CommandTemplate]:
        """
        获取命令模板
        
        Args:
            template_id: 模板ID
            
        Returns:
            命令模板，不存在返回 None
        """
        return self.templates.get(template_id)
    
    def get_all_templates(self) -> list:
        """
        获取所有模板
        
        Returns:
            命令模板列表
        """
        return list(self.templates.values())
    
    def get_template_names(self) -> list:
        """
        获取所有模板名称
        
        Returns:
            模板名称列表
        """
        return [t.name for t in self.templates.values()]
    
    def apply_template(self, template_id: str, **kwargs) -> Optional[str]:
        """
        应用模板
        
        Args:
            template_id: 模板ID
            **kwargs: 参数键值对
            
        Returns:
            替换后的命令字符串，失败返回 None
        """
        template = self.get_template(template_id)
        if not template:
            return None
        
        return template.apply(**kwargs)
