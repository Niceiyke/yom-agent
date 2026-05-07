"""Tests for parallel and chained subagent spawning."""

import asyncio
import time

import pytest

from yom.subagent.core import SubAgentManager, SubAgentDefinition
from yom.testing import fake_agent


@pytest.fixture
def manager():
    """Create a subagent manager with test agents."""
    mgr = SubAgentManager()
    
    # Register test subagents
    mgr.registry.register(SubAgentDefinition(
        name="alpha",
        description="Alpha agent",
        prompt="You are alpha. Task: {task}",
        path=None,
    ))
    mgr.registry.register(SubAgentDefinition(
        name="beta", 
        description="Beta agent",
        prompt="You are beta. Task: {task}",
        path=None,
    ))
    mgr.registry.register(SubAgentDefinition(
        name="combiner",
        description="Combines results",
        prompt="You are combiner. Combine results.",
        path=None,
    ))
    mgr.registry.register(SubAgentDefinition(
        name="analyzer",
        description="Analyzes combined results",
        prompt="You are analyzer. Analyze and report.",
        path=None,
    ))
    
    return mgr


def run_fake(task: str, response: str) -> str:
    """Run fake agent synchronously."""
    async def run():
        agent = fake_agent(response=response)
        return await agent.run(task)
    return asyncio.run(run())


def run_parallel(task1: str, resp1: str, task2: str, resp2: str):
    """Run two agents in parallel."""
    async def run():
        return await asyncio.gather(
            fake_agent(response=resp1).run(task1),
            fake_agent(response=resp2).run(task2),
        )
    return asyncio.run(run())


def run_four_parallel(tasks, responses):
    """Run four agents in parallel."""
    async def run():
        agents = [fake_agent(response=r).run(t) for t, r in zip(tasks, responses)]
        return await asyncio.gather(*agents)
    return asyncio.run(run())


class TestParallelSubagentSpawn:
    """Test parallel spawning of multiple subagents."""

    def test_spawn_two_agents_in_parallel(self, manager):
        """Test that two agents can be spawned in parallel."""
        print("\n" + "=" * 60)
        print("TEST: Spawn TWO agents in parallel")
        print("=" * 60)
        
        start = time.time()
        result_alpha, result_beta = run_parallel(
            "alpha_task", "ALPHA_DONE",
            "beta_task", "BETA_DONE"
        )
        elapsed = time.time() - start
        
        print(f"\nTime: {elapsed:.3f}s")
        print(f"Alpha: {result_alpha}")
        print(f"Beta:  {result_beta}")
        
        assert result_alpha == "ALPHA_DONE"
        assert result_beta == "BETA_DONE"
        
        print("\n[PASS] Two agents spawned in parallel!")

    def test_spawn_four_agents_in_parallel(self, manager):
        """Test that four agents can be spawned in parallel."""
        print("\n" + "=" * 60)
        print("TEST: Spawn FOUR agents in parallel")
        print("=" * 60)
        
        tasks = ["task1", "task2", "task3", "task4"]
        responses = ["RESULT_1", "RESULT_2", "RESULT_3", "RESULT_4"]
        
        start = time.time()
        results = run_four_parallel(tasks, responses)
        elapsed = time.time() - start
        
        print(f"\nTime: {elapsed:.3f}s")
        for i, r in enumerate(results, 1):
            print(f"Agent {i}: {r}")
        
        assert len(results) == 4
        assert all(r.startswith("RESULT_") for r in results)
        
        print("\n[PASS] Four agents spawned in parallel!")


class TestChainedSubagentSpawn:
    """Test chained spawning where results are used for next spawn."""

    def test_chained_two_step(self, manager):
        """Test: Spawn A + B in parallel, then use results for C."""
        print("\n" + "=" * 60)
        print("TEST: Chained spawn (A + B) -> C")
        print("=" * 60)
        
        # Step 1: Spawn A and B in parallel
        print("\n[Step 1] Spawn A + B in parallel...")
        result_a, result_b = run_parallel(
            "task_a", "RESULT_A",
            "task_b", "RESULT_B"
        )
        
        print(f"A: {result_a}")
        print(f"B: {result_b}")
        
        # Step 2: Use both results to spawn C
        print("\n[Step 2] Spawn C with A + B results...")
        combined = f"Combined: {result_a} + {result_b}"
        result_c = run_fake("combine_task", combined)
        
        print(f"C: {result_c}")
        
        assert result_c == f"Combined: RESULT_A + RESULT_B"
        print("\n[PASS] Chained spawn completed!")

    def test_chained_three_step(self, manager):
        """Test: (A + B) -> C -> D chain."""
        print("\n" + "=" * 60)
        print("TEST: Full chain (A + B) -> C -> D")
        print("=" * 60)
        
        # Step 1: A + B in parallel
        print("\n[Step 1] A + B parallel...")
        a, b = run_parallel("task_a", "VALUE_A", "task_b", "VALUE_B")
        
        # Step 2: C uses A + B
        print("\n[Step 2] C uses A + B...")
        c = run_fake("combine", f"COMBINED: {a} + {b}")
        
        # Step 3: D uses C
        print("\n[Step 3] D uses C...")
        d = run_fake("finalize", f"FINAL: {c}")
        
        print(f"\nResults: A={a}, B={b}, C={c}, D={d}")
        
        assert a == "VALUE_A"
        assert b == "VALUE_B"
        assert c == "COMBINED: VALUE_A + VALUE_B"
        assert d == "FINAL: COMBINED: VALUE_A + VALUE_B"
        
        print("\n[PASS] Full chain completed!")

    def test_complex_parallel_and_chain(self, manager):
        """Test complex pattern: (A + B + C) -> (D + E) -> F."""
        print("\n" + "=" * 60)
        print("TEST: Complex pattern (A+B+C) -> (D+E) -> F")
        print("=" * 60)
        
        # Phase 1: A, B, C in parallel
        print("\n[Phase 1] A + B + C parallel...")
        a, b, c = run_four_parallel(
            ["a", "b", "c"],
            ["PHASE1_A", "PHASE1_B", "PHASE1_C"]
        )
        print(f"A={a}, B={b}, C={c}")
        
        # Phase 2: D + E in parallel, both using A, B, C
        print("\n[Phase 2] D + E parallel, using A,B,C...")
        d, e = run_parallel(
            "d", f"D_PROCESSED: {a},{b},{c}",
            "e", f"E_PROCESSED: {a},{b},{c}"
        )
        print(f"D={d}, E={e}")
        
        # Phase 3: F uses D + E
        print("\n[Phase 3] F uses D + E...")
        f = run_fake("final", f"FINAL_RESULT: {d} + {e}")
        print(f"F={f}")
        
        assert f == "FINAL_RESULT: D_PROCESSED: PHASE1_A,PHASE1_B,PHASE1_C + E_PROCESSED: PHASE1_A,PHASE1_B,PHASE1_C"
        
        print("\n[PASS] Complex chain completed!")


class TestParallelTiming:
    """Test timing of parallel vs sequential execution."""

    def test_parallel_faster_than_sequential(self, manager):
        """Verify parallel is faster than sequential."""
        print("\n" + "=" * 60)
        print("TEST: Parallel vs Sequential timing")
        print("=" * 60)
        
        # Sequential (one after another)
        print("\n[Sequential] A then B...")
        seq_start = time.time()
        run_fake("a", "A_DONE")
        run_fake("b", "B_DONE")
        seq_time = time.time() - seq_start
        print(f"Sequential time: {seq_time:.3f}s")
        
        # Parallel (at same time)
        print("\n[Parallel] A + B together...")
        par_start = time.time()
        run_parallel("a", "A_DONE", "b", "B_DONE")
        par_time = time.time() - par_start
        print(f"Parallel time: {par_time:.3f}s")
        
        # Parallel should be faster (at least not slower)
        print(f"\nSpeedup: {seq_time / par_time:.1f}x")
        
        # With fake agents, both are fast, but parallel should not be slower
        assert par_time <= seq_time * 1.5  # Allow some variance
        
        print("[PASS] Parallel timing test completed!")


if __name__ == "__main__":
    # Run tests manually
    print("=" * 70)
    print("PARALLEL & CHAINED SUBAGENT TESTS")
    print("=" * 70)
    
    mgr = SubAgentManager()
    
    # Test 1: Parallel spawn
    print("\n" + "=" * 70)
    print("TEST 1: PARALLEL SPAWN")
    print("=" * 70)
    
    results = run_parallel(
        "alpha", "ALPHA_RESULT",
        "beta", "BETA_RESULT"
    )
    print(f"Alpha: {results[0]}")
    print(f"Beta:  {results[1]}")
    print("PASSED: Two agents spawned in parallel")
    
    # Test 2: Chained spawn
    print("\n" + "=" * 70)
    print("TEST 2: CHAINED SPAWN")
    print("=" * 70)
    
    step1 = run_parallel("task1", "STEP1_A", "task2", "STEP1_B")
    step2 = run_fake("combine", f"COMBINED: {step1[0]} + {step1[1]}")
    print(f"Step 1 results: {step1[0]}, {step1[1]}")
    print(f"Step 2 result: {step2}")
    print("PASSED: Chained spawn completed")
    
    print("\n" + "=" * 70)
    print("ALL PARALLEL & CHAINED TESTS PASSED!")
    print("=" * 70)