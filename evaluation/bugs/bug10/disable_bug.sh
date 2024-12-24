#!/bin/bash

FILE="../../../thirdPart/nova-chipmunk-disable-chipmunk-bugs/nova_def.h"
# Add '//' to disable the bug
sed -i 's/^\(#define Silhouette_NOVA_BUG_149\)/\/\/ \1/' "$FILE"
