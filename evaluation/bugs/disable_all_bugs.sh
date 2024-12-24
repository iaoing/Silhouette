#!/bin/bash

# Add '//'
sed -i 's/^\(#define Silhouette_NOVA_BUG\)/\/\/ \1/' ../../thirdPart/nova-chipmunk-disable-chipmunk-bugs/nova_def.h
