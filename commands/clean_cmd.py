"""clean — (stretch) bulk terminate resources matching a tag.

WARNING — DESIGN-FOR-SAFETY
---------------------------
This is the most dangerous command in the CLI. Get the contract right:

  1. DEFAULT IS DRY-RUN. Without --apply the command MUST NOT touch resources.
     It only lists what WOULD be deleted.
  2. Even with --apply, you should consider printing a summary count first
     ("about to terminate N EC2 + M volumes — proceed?"), though for this
     starter a hard `--apply` flag is enough.
  3. Never use this with a tag you don't fully own. Reflection prompt in
     README covers the blast-radius scenario.

WHAT YOU MUST BUILD
-------------------
1. `_find_targets(tag_key, tag_val)` — return a dict like:
     {"ec2": [<instance ids in non-terminal state>],
      "volume": [<volume ids in 'available' state only>]}
   Skip terminated/shutting-down instances (already gone).
   Skip in-use volumes (can't delete while attached — would error anyway).

2. `run(args)` — call _find_targets, print the plan, then either:
     - bail with "(dry-run — pass --apply to ...)"  (default)
     - or actually terminate (when --apply)

HELPERS YOU CAN USE
-------------------
From commands._common:
  parse_kv(s) -> (k, v)

AWS APIS YOU'LL NEED
--------------------
- ec2.describe_instances() + describe_volumes() — same as list_cmd
- ec2.terminate_instances(InstanceIds=[...])
- ec2.delete_volume(VolumeId=...)  (per volume, no bulk API)

VERIFY
------
    pytest tests/test_clean.py -v
"""
import boto3

from commands._common import parse_kv, tags_to_dict, tags_match


TERMINAL_STATES = {"terminated", "shutting-down"}


def _find_targets(tag_key, tag_val):
    """Return {"ec2": [...], "volume": [...]} matching tag in non-terminal state."""
    ec2 = boto3.client("ec2")
    want = [(tag_key, tag_val)]

    # Find EC2 instances matching tag, skip terminated/shutting-down
    ec2_ids = []
    paginator = ec2.get_paginator("describe_instances")
    for page in paginator.paginate():
        for reservation in page["Reservations"]:
            for inst in reservation["Instances"]:
                state = inst["State"]["Name"]
                if state in TERMINAL_STATES:
                    continue
                tags = tags_to_dict(inst.get("Tags"))
                if tags_match(tags, want, []):
                    ec2_ids.append(inst["InstanceId"])

    # Find EBS volumes matching tag, only 'available' state
    vol_ids = []
    vol_paginator = ec2.get_paginator("describe_volumes")
    for page in vol_paginator.paginate():
        for vol in page["Volumes"]:
            if vol["State"] != "available":
                continue
            tags = tags_to_dict(vol.get("Tags"))
            if tags_match(tags, want, []):
                vol_ids.append(vol["VolumeId"])

    return {"ec2": ec2_ids, "volume": vol_ids}


def run(args):
    """Entry point.

    Args set by argparse:
        args.tag    — "key=value" string (REQUIRED)
        args.apply  — bool, must be True to actually delete (default False = dry-run)
    """
    tag_key, tag_val = parse_kv(args.tag)
    targets = _find_targets(tag_key, tag_val)

    total = len(targets["ec2"]) + len(targets["volume"])
    if total == 0:
        print(f"Nothing to clean for {tag_key}={tag_val}.")
        return

    # Print plan
    print(f"Clean targets for {tag_key}={tag_val}:")
    print("-" * 60)
    if targets["ec2"]:
        print(f"  EC2 instances ({len(targets['ec2'])}):")
        for iid in targets["ec2"]:
            print(f"    {iid}")
    if targets["volume"]:
        print(f"  EBS volumes ({len(targets['volume'])}):")
        for vid in targets["volume"]:
            print(f"    {vid}")
    print("-" * 60)

    if not args.apply:
        print(f"(dry-run — pass --apply to terminate {total} resource(s))")
        return

    # Apply: terminate EC2 instances
    ec2 = boto3.client("ec2")
    if targets["ec2"]:
        ec2.terminate_instances(InstanceIds=targets["ec2"])
        for iid in targets["ec2"]:
            print(f"Terminated EC2 {iid}")

    # Apply: delete available volumes
    for vid in targets["volume"]:
        ec2.delete_volume(VolumeId=vid)
        print(f"Deleted volume {vid}")
