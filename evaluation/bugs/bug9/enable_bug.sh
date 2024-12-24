#!/bin/bash

FILE="../../../thirdPart/nova-chipmunk-disable-chipmunk-bugs/nova_def.h"
# Remove '//' to enable the bug
sed -i 's|^//[[:space:]]\(#define Silhouette_NOVA_BUG_137\)|\1|' "$FILE"
