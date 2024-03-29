IMAGE_NAME:=europe-docker.pkg.dev/nube-hub/docker-public/velo-action
SHELL := /bin/bash

.PHONY: version tests version_semver

version_semver:
	docker run --rm -v "$(PWD):/repo" gittools/gitversion:5.10.1-alpine.3.14-6.0 /repo /showvariable SemVer > version.txt

# The version command is split in to. Forst generate it then read.
# If these are the same command the echo part will read the "old" version, and create confusion.
version: version_semver
	echo "Version: $(shell cat version.txt)"

tests:
	poetry run pytest velo_action -c pytest.ini -v -m "not docker"

image: version
	docker build -t ${IMAGE_NAME}:$(shell cat version.txt) .
	docker tag ${IMAGE_NAME}:$(shell cat version.txt) ${IMAGE_NAME}:dev

push: image
	docker push ${IMAGE_NAME}:$(shell cat version.txt)
	docker push ${IMAGE_NAME}:dev

run:
	. ./env.dev && poetry run python velo_action/main.py

run_docker:
	. ./env.dev && docker-compose build && docker-compose run --rm velo-action

run_docker_shell:
	. ./env.dev && docker-compose build && docker-compose run --rm --entrypoint bash velo-action

velo_render_dev:
	velo render -e dev

velo_deploy_dev:
	velo deploy -e dev

velo_render_staging:
	velo render -e staging

velo_deploy_staging:
	velo deploy -e staging

velo_render_prod:
	velo render -e prod

velo_deploy_prod:
	velo deploy -e prod

tfi:
	cd temp-deploy/terraform && terraform init

tfa: tfi
	cd temp-deploy/terraform && terraform apply -var-file=values.json

lint: black flake8 mypy pylint yamllint isort markdownlint

black:
	poetry run black --config=pyproject.toml .

flake8:
	poetry run flake8 --config='.flake8' .

mypy:
	poetry run mypy --config-file=.mypy.ini velo_action

pylint:
	poetry run pylint --rcfile=.pylintrc --fail-under=10 velo_action

isort:
	poetry run isort .

yamllint:
	yamllint --config-file=.yamllint .

markdownlint:
	markdownlint --config=.markdownlint.yaml .

install:
	poetry install

docs_generate:
	techdocs-cli generate --verbose --no-docker

# The 'mkdocs-click' is not installed in the techdocs docker image
docs: docs_generate
	techdocs-cli serve --verbose --no-docker

# require access to nube-centro-prod
docs_publish_prod: docs_generate
	techdocs-cli publish \
	--publisher-type googleGcs \
	--storage-name centro-docs-prod \
	--entity "default/Component/velo-action"

# require access to nube-centro-staging
docs_publish_staging: docs_generate
	techdocs-cli publish \
	--publisher-type googleGcs \
	--storage-name centro-docs-staging \
	--entity "default/Component/velo-action"

# Kill the mkdocs server
# kill -9 $(lsof -ti:8000)
mkdocs:
	mkdocs serve --verbose
