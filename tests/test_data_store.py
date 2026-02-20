"""
Tests for the DataStore (tag database).
"""

import pytest
from plc.core.data_store import DataStore


class TestDataStore:
    """Test tag read/write and thread safety."""

    def test_read_default_tags(self, data_store):
        assert data_store.read("LACT_STATE") == "IDLE"
        assert data_store.read("DI_ESTOP") is False
        assert data_store.read("FLOW_RATE_BPH") == 0.0

    def test_write_and_read(self, data_store):
        data_store.write("FLOW_RATE_BPH", 123.456)
        assert data_store.read("FLOW_RATE_BPH") == 123.456

    def test_read_nonexistent_tag(self, data_store):
        assert data_store.read("NONEXISTENT") is None

    def test_write_creates_tag(self, data_store):
        data_store.write("NEW_TAG", 42)
        assert data_store.read("NEW_TAG") == 42

    def test_read_with_quality(self, data_store):
        data_store.write("AI_BSW_PROBE", 0.5, quality="BAD")
        tv = data_store.read_with_quality("AI_BSW_PROBE")
        assert tv.value == 0.5
        assert tv.quality == "BAD"
        assert tv.timestamp > 0

    def test_read_multiple(self, data_store):
        data_store.write("A", 1)
        data_store.write("B", 2)
        result = data_store.read_multiple(["A", "B", "C"])
        assert result["A"] == 1
        assert result["B"] == 2
        assert "C" not in result

    def test_write_multiple(self, data_store):
        data_store.write_multiple({"X": 10, "Y": 20})
        assert data_store.read("X") == 10
        assert data_store.read("Y") == 20

    def test_get_all_tags(self, data_store):
        tags = data_store.get_all_tags()
        assert "LACT_STATE" in tags
        assert "DI_ESTOP" in tags

    def test_tag_exists(self, data_store):
        assert data_store.tag_exists("LACT_STATE")
        assert not data_store.tag_exists("FAKE_TAG")

    def test_boolean_tags(self, data_store):
        data_store.write("DI_ESTOP", True)
        assert data_store.read("DI_ESTOP") is True
        data_store.write("DI_ESTOP", False)
        assert data_store.read("DI_ESTOP") is False
