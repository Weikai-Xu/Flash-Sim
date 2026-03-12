if __package__ in (None, ""):
    import os
    import sys

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    from flash_sim.engine import Engine
else:
    from .engine import Engine


if __name__ == "__main__":
    sim_engine = Engine()
    sim_engine.Start_simulation()