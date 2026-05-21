import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from utils.path_resolver import PathResolver, PathScope, get_app_dir, get_data_dir, get_rules_path, get_tools_dir


class TestGetAppDir:

    def test_source_mode(self):
        with patch.object(sys, "frozen", False, create=True):
            result = PathResolver.get_app_dir()
            assert isinstance(result, Path)
            assert result.exists()

    def test_frozen_mode(self, tmp_path):
        fake_exe = tmp_path / "IRtool.exe"
        fake_exe.write_text("")
        with patch.object(sys, "frozen", True, create=True):
            with patch.object(sys, "executable", str(fake_exe)):
                result = PathResolver.get_app_dir()
                assert result == tmp_path


class TestGetDataDir:

    def test_data_dir_exists(self):
        result = PathResolver.get_data_dir()
        assert isinstance(result, Path)
        assert result.name == "data"

    def test_data_dir_fallback_internal(self, tmp_path):
        internal_dir = tmp_path / "_internal" / "data"
        internal_dir.mkdir(parents=True)
        with patch.object(PathResolver, "get_app_dir", return_value=tmp_path):
            result = PathResolver.get_data_dir()
            assert result == internal_dir

    def test_data_dir_fallback_default(self, tmp_path):
        with patch.object(PathResolver, "get_app_dir", return_value=tmp_path):
            result = PathResolver.get_data_dir()
            assert result == tmp_path / "data"


class TestGetRulesPath:

    def test_rules_path(self):
        result = PathResolver.get_rules_path()
        assert isinstance(result, Path)
        assert result.name == "rules.json"


class TestGetToolsDir:

    def test_tools_dir_exists(self):
        result = PathResolver.get_tools_dir()
        assert isinstance(result, Path)
        assert result.name == "tools"

    def test_tools_dir_fallback_internal(self, tmp_path):
        internal_dir = tmp_path / "_internal" / "tools"
        internal_dir.mkdir(parents=True)
        with patch.object(PathResolver, "get_app_dir", return_value=tmp_path):
            result = PathResolver.get_tools_dir()
            assert result == internal_dir


class TestResolve:

    def test_resolve_self(self, tmp_path):
        test_file = tmp_path / "test.exe"
        test_file.write_text("")
        result = PathResolver.resolve(str(test_file), PathScope.SELF)
        assert result == str(test_file)

    def test_resolve_directory(self, tmp_path):
        test_file = tmp_path / "test.exe"
        test_file.write_text("")
        result = PathResolver.resolve(str(test_file), PathScope.DIRECTORY)
        assert result == str(tmp_path)

    def test_resolve_parent(self, tmp_path):
        sub_dir = tmp_path / "sub"
        sub_dir.mkdir()
        test_file = sub_dir / "test.exe"
        test_file.write_text("")
        result = PathResolver.resolve(str(test_file), PathScope.PARENT)
        assert result == str(tmp_path)

    def test_resolve_empty_path(self):
        result = PathResolver.resolve("", PathScope.SELF)
        assert result == ""

    def test_resolve_nonexistent_path(self):
        result = PathResolver.resolve(r"C:\nonexistent\path\file.exe", PathScope.SELF)
        assert result == r"C:\nonexistent\path\file.exe"

    def test_resolve_directory_scope_on_dir(self, tmp_path):
        result = PathResolver.resolve(str(tmp_path), PathScope.DIRECTORY)
        assert result == str(tmp_path)

    def test_resolve_parent_scope_on_dir(self, tmp_path):
        sub_dir = tmp_path / "sub"
        sub_dir.mkdir()
        result = PathResolver.resolve(str(sub_dir), PathScope.PARENT)
        assert result == str(tmp_path)


class TestModuleLevelFunctions:

    def test_get_app_dir_function(self):
        result = get_app_dir()
        assert isinstance(result, Path)

    def test_get_data_dir_function(self):
        result = get_data_dir()
        assert isinstance(result, Path)

    def test_get_rules_path_function(self):
        result = get_rules_path()
        assert isinstance(result, Path)

    def test_get_tools_dir_function(self):
        result = get_tools_dir()
        assert isinstance(result, Path)
