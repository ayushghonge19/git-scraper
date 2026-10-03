"""Automated verification script for Phase 2: MongoDB Checkpointing & Thread Isolation.

Runs 3 distinct subprocesses (simulating full application restarts) to verify:
1. Thread 'demo': Teach the assistant "My main project is DisasterLAN." -> Exit app.
2. Restart app with Thread 'demo': Ask "What is my main project?" -> Verifies memory restored!
3. Restart app with Thread 'thread-B': Ask "What is my main project?" -> Verifies thread isolation (thread-A != thread-B)!
"""

import subprocess
import sys


def run_session(thread_id: str, inputs: list[str]) -> str:
    """Runs main.py in a fresh subprocess and feeds user inputs."""
    cmd = [sys.executable, "main.py", "--thread", thread_id]
    input_text = "\n".join(inputs) + "\nexit\n"

    process = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    stdout, stderr = process.communicate(input_text)
    return stdout


def main():
    print("=" * 65)
    print(" Phase 2: Automated Verification of MongoDB Persistence & Threads")
    print("=" * 65)

    # --- STEP 1: Process 1 (Thread demo) ---
    print("\n[Step 1] Starting Application with thread_id='demo'...")
    out1 = run_session(
        "demo", ["My main project is DisasterLAN. Please acknowledge briefly."]
    )
    print("Session 1 Output:")
    for line in out1.splitlines():
        if "You:" in line or "Assistant:" in line or "Active Thread:" in line:
            print("  ", line)

    # --- STEP 2: Process 2 (Restarting with Thread demo) ---
    print("\n[Step 2] RESTARTING Application with thread_id='demo'...")
    out2 = run_session("demo", ["What is my main project? Answer in 1-2 words."])
    print("Session 2 Output (After Restart):")
    for line in out2.splitlines():
        if (
            "You:" in line
            or "Assistant:" in line
            or "Active Thread:" in line
            or "Restored" in line
        ):
            print("  ", line)

    assert (
        "disasterlan" in out2.lower()
    ), "Assertion Failed: 'DisasterLAN' was not remembered after application restart!"
    print(">>> SUCCESS: Assistant remembered 'DisasterLAN' across restart!")

    # --- STEP 3: Process 3 (Starting with Thread thread-B) ---
    print("\n[Step 3] Starting Application with thread_id='thread-B' (Isolation Test)...")
    out3 = run_session("thread-B", ["What is my main project?"])
    print("Session 3 Output (Thread Isolation):")
    for line in out3.splitlines():
        if "You:" in line or "Assistant:" in line or "Active Thread:" in line:
            print("  ", line)

    assert (
        "disasterlan" not in out3.lower()
    ), "Assertion Failed: thread-B should NOT know about DisasterLAN from thread 'demo'!"
    print(">>> SUCCESS: thread-B has NO knowledge of thread 'demo' (thread-A != thread-B)!")

    print("\n" + "=" * 65)
    print(" All Phase 2 Persistence & Thread Isolation Assertions Passed!")
    print("=" * 65)


if __name__ == "__main__":
    main()
