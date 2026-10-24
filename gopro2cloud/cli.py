"""
gopro2cloud.cli - Backwards compatibility wrapper re-exporting from unicloud.cli.
"""

from unicloud.cli import (
    main_gopro_legacy as main,
    main_cloudsync,
    cmd_status,
    cmd_list,
    cmd_sync,
    format_size,
)

if __name__ == "__main__":
    main()
