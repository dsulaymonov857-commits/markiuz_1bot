"""Continuous Bot Runner with Auto-Restart Watchdog."""

import logging
import subprocess
import sys
import time
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [WATCHDOG] %(message)s",
)
logger = logging.getLogger("Watchdog")

ROOT_DIR = Path(__file__).resolve().parent.parent
PYTHON_EXE = sys.executable


def run_forever():
    logger.info("Starting bot process supervisor...")
    restart_count = 0

    while True:
        try:
            logger.info("Launching bot instance #%d...", restart_count + 1)
            process = subprocess.Popen(
                [PYTHON_EXE, "-m", "app.main"],
                cwd=str(ROOT_DIR),
            )
            return_code = process.wait()
            restart_count += 1

            if return_code == 0:
                logger.info("Bot exited cleanly (code 0). Restarting in 2 seconds...")
            else:
                logger.warning(
                    "Bot stopped with exit code %s. Restarting in 5 seconds...",
                    return_code,
                )
            time.sleep(3)
        except KeyboardInterrupt:
            logger.info("Watchdog terminated by user. Stopping bot...")
            if process.poll() is None:
                process.terminate()
                process.wait()
            break
        except Exception as exc:
            logger.error("Watchdog error: %s. Retrying in 5 seconds...", exc)
            time.sleep(5)


if __name__ == "__main__":
    run_forever()
