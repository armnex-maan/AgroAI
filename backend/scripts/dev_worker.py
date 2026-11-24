"""Run the simulation worker in dev mode."""
import devenv

devenv.apply()

from app.simulation.worker import loop  # noqa: E402

if __name__ == "__main__":
    loop()
