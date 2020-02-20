.PHONY: shell flake test

ifeq ($(GIT),)
  GIT := $(HOME)/git
endif

IMAGE := base-python

NET := --net test
MOUNT := /opt/git
VOLUMES := -v=$(GIT):$(MOUNT)
WORKING := -w $(MOUNT)/aiomicro
PYTHONPATH := -e PYTHONPATH=$(MOUNT)/ergaleia:$(MOUNT)/fsm:$(MOUNT)/aiodb:.

DOCKER := docker run --rm -it $(VOLUMES) $(PYTHONPATH) $(WORKING) $(NET) $(IMAGE)

shell:
	$(DOCKER) bash

flake:
	$(DOCKER) flake8

test:
	$(DOCKER) pytest
