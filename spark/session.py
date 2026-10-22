"""
Shared SparkSession builder for every PySpark job in this project.

Falls back to the portable JDK bundled in .tools/ (see README) if no
system Java is on PATH, and binds Spark to the loopback interface, which
this project's dev environment needs. All jobs built on this session
deliberately avoid Python UDFs — see spark/clean.py for why — so they
run entirely inside the JVM without needing a Python worker subprocess.
"""

import os
from pathlib import Path

from pyspark.sql import SparkSession

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = PROJECT_ROOT / ".tools"


def _find_bundled_java_home():
    """Finds a portable JDK under .tools/ (see scripts/setup_java.py), whatever its exact version folder name is."""
    candidates = sorted(TOOLS_DIR.glob("jdk-*"))
    return candidates[0] if candidates else None


def get_spark_session(app_name: str = "social-media-sentiment") -> SparkSession:
    if "JAVA_HOME" not in os.environ:
        bundled = _find_bundled_java_home()
        if bundled:
            os.environ["JAVA_HOME"] = str(bundled)
    os.environ.setdefault("SPARK_LOCAL_IP", "127.0.0.1")

    return (
        SparkSession.builder.appName(app_name)
        .master("local[*]")
        .config("spark.ui.enabled", "false")
        .config("spark.driver.host", "127.0.0.1")
        .config("spark.sql.shuffle.partitions", "4")  # small demo dataset; default 200 is overkill
        .getOrCreate()
    )
