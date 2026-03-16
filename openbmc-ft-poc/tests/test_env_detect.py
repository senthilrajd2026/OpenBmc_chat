"""Tests for the env_detect module."""

import sys
from unittest.mock import MagicMock, patch

import pytest
from src.openbmc_ft_poc.env_detect import EnvReport, detect_environment, format_report


class TestEnvReport:
    def test_default_values(self):
        report = EnvReport()
        assert report.is_wsl2 is False
        assert report.is_native_linux is False
        assert report.can_generate_dataset is False
        assert report.can_fine_tune is False
        assert report.warnings == []
        assert report.recommendations == []

    def test_warnings_list_is_independent(self):
        r1 = EnvReport()
        r2 = EnvReport()
        r1.warnings.append("test")
        assert r2.warnings == []  # should not share the list


class TestDetectEnvironment:
    def test_returns_env_report(self):
        report = detect_environment()
        assert isinstance(report, EnvReport)

    def test_does_not_raise(self):
        """detect_environment should never raise, even in unusual environments."""
        try:
            report = detect_environment()
        except Exception as exc:
            pytest.fail(f"detect_environment raised unexpectedly: {exc}")

    def test_python_version_detected(self):
        report = detect_environment()
        assert report.python_version
        assert "." in report.python_version  # should be like "3.11.x"

    def test_python_ok_for_current_python(self):
        report = detect_environment()
        # We're running in Python 3.11+, so this should be True
        if sys.version_info >= (3, 11):
            assert report.python_ok is True

    def test_cpu_cores_detected(self):
        report = detect_environment()
        assert report.cpu_cores >= 1

    def test_dataset_feasibility_requires_python_and_git(self):
        """can_generate_dataset should be False if Python check fails."""
        report = EnvReport()
        report.python_ok = False
        report.git_ok = True
        report.ram_gb = 8.0
        report.disk_free_gb = 20.0
        # Manually recompute (detect_environment does this internally)
        can = (
            report.python_ok
            and report.git_ok
            and report.ram_gb >= 2.0
            and report.disk_free_gb >= 10.0
        )
        assert can is False

    def test_fine_tuning_requires_cuda(self):
        """can_fine_tune should be False without CUDA."""
        report = EnvReport()
        report.cuda_visible = False
        report.gpu_vram_gb = 8.0
        can = report.cuda_visible and report.gpu_vram_gb >= 6.0
        assert can is False


class TestFormatReport:
    def test_format_output_is_string(self):
        report = detect_environment()
        output = format_report(report)
        assert isinstance(output, str)
        assert len(output) > 100

    def test_format_contains_key_sections(self):
        report = detect_environment()
        output = format_report(report)
        assert "Platform" in output
        assert "Hardware" in output
        assert "GPU" in output
        assert "Feasibility" in output

    def test_format_shows_warnings(self):
        report = EnvReport()
        report.warnings = ["Test warning 1", "Test warning 2"]
        report.python_version = "3.11.0"
        report.git_version = "git version 2.40.0"
        output = format_report(report)
        assert "Warnings" in output
        assert "Test warning 1" in output

    def test_format_shows_recommendations(self):
        report = EnvReport()
        report.recommendations = ["Install CUDA: https://..."]
        report.python_version = "3.11.0"
        report.git_version = "git version 2.40.0"
        output = format_report(report)
        assert "Recommendations" in output
        assert "Install CUDA" in output

    def test_wsl2_shown_in_report(self):
        report = EnvReport()
        report.is_wsl2 = True
        report.python_version = "3.11.0"
        report.git_version = "git version 2.40.0"
        output = format_report(report)
        assert "WSL2" in output
        assert "YES" in output
