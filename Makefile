# Local development
run:
	python handler.py

# Serverless Framework targets
sls-deploy:
	serverless deploy --stage prod

sls-deploy-with-slack:
	serverless deploy --stage prod --param "slack_url=$(SLACK_URL)"

sls-invoke:
	serverless invoke --function report_cost --stage prod

sls-remove:
	serverless remove --stage prod

# AWS SAM targets
sam-build:
	sam build

sam-deploy:
	sam deploy

sam-deploy-guided:
	sam deploy --guided

sam-deploy-with-slack:
	sam deploy --parameter-overrides SlackWebhookUrl="$(SLACK_URL)"

sam-deploy-with-params:
	sam deploy --parameter-overrides \
		SlackWebhookUrl="$(SLACK_URL)" \
		GroupBy="$(GROUP_BY)" \
		GroupLength=$(GROUP_LENGTH) \
		AwsAccountName="$(AWS_ACCOUNT_NAME)"

# SAM Profile-specific deployments
sam-deploy-account:
	sam deploy --config-env account

sam-deploy-service:
	sam deploy --config-env service

sam-deploy-both: sam-deploy-account sam-deploy-service

sam-delete-account:
	sam delete --config-env account

sam-delete-service:
	sam delete --config-env service

sam-local-invoke:
	sam local invoke ReportCostFunction

sam-local-start-api:
	sam local start-api

sam-delete:
	sam delete

# Utility targets
install-serverless:
	npm install -g serverless
	serverless plugin install -n serverless-python-requirements

install-sam:
	@echo "Please install AWS SAM CLI from: https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-install.html"

help:
	@echo "Available targets:"
	@echo "  run                    - Run the handler locally"
	@echo ""
	@echo "Serverless Framework:"
	@echo "  sls-deploy            - Deploy with Serverless Framework"
	@echo "  sls-deploy-with-slack - Deploy with Slack webhook (set SLACK_URL)"
	@echo "  sls-invoke            - Test the deployed function"
	@echo "  sls-remove            - Remove the Serverless deployment"
	@echo "  install-serverless    - Install Serverless Framework and plugins"
	@echo ""
	@echo "AWS SAM:"
	@echo "  sam-build             - Build the SAM application"
	@echo "  sam-deploy            - Deploy with SAM (uses default profile)"
	@echo "  sam-deploy-guided     - Deploy with guided setup"
	@echo "  sam-deploy-with-slack - Deploy with Slack webhook (set SLACK_URL)"
	@echo "  sam-deploy-with-params - Deploy with multiple parameters"
	@echo ""
	@echo "SAM Profile Deployments:"
	@echo "  sam-deploy-account    - Deploy account profile (LINKED_ACCOUNT grouping, 20 items)"
	@echo "  sam-deploy-service    - Deploy service profile (LINKED_ACCOUNT grouping, 10 items)"
	@echo "  sam-delete-account    - Delete account profile stack"
	@echo "  sam-delete-service    - Delete service profile stack"
	@echo ""
	@echo "SAM Local/Testing:"
	@echo "  sam-local-invoke      - Test function locally"
	@echo "  sam-local-start-api   - Start local API Gateway"
	@echo "  sam-delete            - Delete the default SAM stack"
	@echo "  install-sam           - Show SAM CLI installation instructions"
	@echo ""
	@echo "Example usage:"
	@echo "  make sam-deploy-account    # Deploy with account breakdown"
	@echo "  make sam-deploy-service    # Deploy with service breakdown"
	@echo "  make sam-deploy-with-slack SLACK_URL='https://hooks.slack.com/services/xxx/yyy/zzz'"

.PHONY: run sls-deploy sls-deploy-with-slack sls-invoke sls-remove sam-build sam-deploy sam-deploy-guided sam-deploy-with-slack sam-deploy-with-params sam-deploy-account sam-deploy-service sam-delete-account sam-delete-service sam-local-invoke sam-local-start-api sam-delete install-serverless install-sam help