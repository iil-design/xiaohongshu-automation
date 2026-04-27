import os
import sys
import urllib.request
import urllib.parse

BASE = "http://127.0.0.1:8000"


def test_index():
    resp = urllib.request.urlopen(f"{BASE}/")
    assert resp.status == 200, f"Expected 200, got {resp.status}"
    body = resp.read().decode("utf-8")
    assert "帖子管理" in body, "Missing 帖子管理 in index"
    assert "新建帖子" in body, "Missing 新建帖子 in index"


def test_editor():
    resp = urllib.request.urlopen(f"{BASE}/editor")
    assert resp.status == 200, f"Expected 200, got {resp.status}"


def test_history():
    resp = urllib.request.urlopen(f"{BASE}/history")
    assert resp.status == 200, f"Expected 200, got {resp.status}"


def test_create_draft():
    data = urllib.parse.urlencode({
        "title": "测试帖子",
        "body": "这是一条测试内容",
        "action": "draft",
    }).encode("utf-8")
    req = urllib.request.Request(f"{BASE}/posts/create", data=data, method="POST")
    resp = urllib.request.urlopen(req)
    assert resp.status == 200, f"Expected 200, got {resp.status}"

    resp2 = urllib.request.urlopen(f"{BASE}/")
    body = resp2.read().decode("utf-8")
    assert "测试帖子" in body, "Created post not found in index"


if __name__ == "__main__":
    test_index()
    print("PASS: test_index")
    test_editor()
    print("PASS: test_editor")
    test_history()
    print("PASS: test_history")
    test_create_draft()
    print("PASS: test_create_draft")
    print("ALL TESTS PASSED")
