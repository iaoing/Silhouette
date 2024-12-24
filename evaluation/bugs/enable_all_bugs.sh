#!/bin/bash

# Remove '//'
sed -i 's|^//[[:space:]]\(#define Silhouette_NOVA_BUG\)|\1|' ../../thirdPart/nova-chipmunk-disable-chipmunk-bugs/nova_def.h
