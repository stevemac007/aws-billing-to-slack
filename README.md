# AWS Billing to Slack

![image](https://user-images.githubusercontent.com/261584/66362145-3903a200-e947-11e9-91bd-6e40e5919ac4.png)

Sends daily breakdowns of AWS costs to a Slack channel.

## Requirements

- Python 3.12+ (uses modern Python features and type hints)
- AWS CLI configured with appropriate permissions
- Node.js (for Serverless Framework) OR AWS SAM CLI

# Deployment Options

This project supports two deployment methods:
1. **Serverless Framework** (original method)
2. **AWS SAM** (new option)

Choose the method that best fits your workflow and tooling preferences.

## Option 1: Serverless Framework Deployment

### Prerequisites

1. Install [`serverless`](https://serverless.com/), which configures the AWS Lambda function that runs daily.

    ```bash
    npm install -g serverless
    ```

2. Create an [incoming webhook](https://www.slack.com/apps/new/A0F7XDUAZ) that will post to the channel of your choice on your Slack workspace. Grab the URL for use in the next step.

### Deploy with Serverless

1. **Create the service on your local machine:**

    ```bash
    serverless create \
      --template-url="https://github.com/iandees/aws-billing-to-slack.git" \
      --path="app-aws-cost" \
      --name="app-aws-cost"
    ```

2. **Install pipenv:**

    ```bash
    pip install pipenv==2023.7.4
    ```

3. **Install serverless python requirements:**

    ```bash
    serverless plugin install -n serverless-python-requirements
    ```

4. **Deploy the system into your AWS account:**

    ```bash
    serverless deploy --stage="prod" --param="slack_url=https://hooks.slack.com/services/xxx/yyy/zzzz"
    ```

5. **Test the function:**

    ```bash
    serverless invoke --function report_cost --stage="prod" --param="slack_url=https://hooks.slack.com/services/xxx/yyy/zzzz"
    ```

## Option 2: AWS SAM Deployment

### Prerequisites

1. Install [AWS SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-install.html)
2. Configure AWS CLI with appropriate permissions
3. Create a [Slack incoming webhook](https://www.slack.com/apps/new/A0F7XDUAZ) for your channel

### Deploy with SAM

1. **Build the application:**
   ```bash
   sam build
   ```

2. **Deploy with guided setup (first time):**
   ```bash
   sam deploy --guided
   ```
   
   You'll be prompted for parameters including:
   - Stack name (e.g., `aws-billing-to-slack`)
   - AWS Region
   - SlackWebhookUrl (your Slack webhook URL)
   - Other optional parameters (GroupBy, GroupLength, etc.)

3. **Deploy with parameters (subsequent deployments):**
   ```bash
   sam deploy --parameter-overrides \
     SlackWebhookUrl="https://hooks.slack.com/services/xxx/yyy/zzzz" \
     GroupBy="SERVICE" \
     GroupLength=10
   ```

4. **Test the function:**
   ```bash
   sam local invoke ReportCostFunction
   ```

### SAM Parameters

All Serverless parameters are available as SAM parameters:

- `SlackWebhookUrl`: Slack webhook URL
- `TeamsWebhookUrl`: Microsoft Teams webhook URL  
- `GoogleWebhookUrl`: Google Chat webhook URL
- `GroupBy`: Dimension to group by (default: SERVICE)
- `GroupLength`: Number of top services to show (default: 10)
- `AwsAccountName`: Custom account name for display
- `CreditsExpireDate`: AWS credits expiration (mm/dd/yyyy)
- `CreditsRemainingAsOf`: Credits calculation date (mm/dd/yyyy)
- `CreditsRemaining`: Remaining credits amount
- `CostAggregation`: Cost method (default: UnblendedCost)
- `Days`: Days to include in report (default: 7)

### Example SAM deployment with AWS credits:

```bash
sam deploy --parameter-overrides \
  SlackWebhookUrl="https://hooks.slack.com/services/xxx/yyy/zzzz" \
  CreditsExpireDate="12/31/2024" \
  CreditsRemainingAsOf="01/15/2024" \
  CreditsRemaining="500.00"
```

### Example SAM deployment for AWS Organization (by account):

```bash
sam deploy --parameter-overrides \
  SlackWebhookUrl="https://hooks.slack.com/services/xxx/yyy/zzzz" \
  GroupBy="LINKED_ACCOUNT" \
  GroupLength=15
```

## Deployment Method Comparison

| Feature | Serverless Framework | AWS SAM |
|---------|---------------------|---------|
| **Configuration** | `serverless.yml` | `template.yaml` |
| **Dependencies** | Node.js + Serverless CLI | AWS SAM CLI |
| **Parameter Handling** | Command-line `--param` | CloudFormation parameters |
| **Local Testing** | `serverless invoke local` | `sam local invoke` |
| **AWS Integration** | Third-party framework | Native AWS tooling |
| **Template Format** | Serverless-specific YAML | CloudFormation + SAM |

Both methods deploy the same Lambda function with identical functionality. Choose based on your team's preferences and existing toolchain.

## Support for AWS Credits (Both Methods)

If you have AWS credits on your account and want to see them taken into account on this report, head to [your billing dashboard](https://console.aws.amazon.com/billing/home?#/credits) and note down the "Expiration Date", "Amount Remaining", and the "as of" date towards the bottom of the page. Add all three of these items to the command line when executing the `deploy` or `invoke`:

    ```
    serverless deploy \
        --param "slack_url=https://hooks.slack.com/services/xxx/yyy/zzzz" \
        --param "credits_expire_date=mm/dd/yyyy" \
        --param "credits_remaining_date=mm/dd/yyyy" \
        --param "credits_remaining=xxx.xx"
    ```

## Support for other Dimensions (Both Methods)

If you have an AWS Organization and would like to see a breakdown by account, you can override the default dimensions:

**Serverless Framework:**
```bash
serverless deploy \
    --param "slack_url=https://hooks.slack.com/services/xxx/yyy/zzzz" \
    --param "group=LINKED_ACCOUNT" \
    --param "group_length=15"
```

**AWS SAM:**
```bash
sam deploy --parameter-overrides \
    SlackWebhookUrl="https://hooks.slack.com/services/xxx/yyy/zzzz" \
    GroupBy="LINKED_ACCOUNT" \
    GroupLength=15
```

Possible value for `group` are:

* AZ
* INSTANCE_TYPE
* LINKED_ACCOUNT
* OPERATION
* PURCHASE_TYPE
* SERVICE
* USAGE_TYPE
* PLATFORM
* TENANCY
* RECORD_TYPE
* LEGAL_ENTITY_NAME
* INVOICING_ENTITY
* DEPLOYMENT_OPTION
* DATABASE_ENGINE
* CACHE_ENGINE
* INSTANCE_TYPE_FAMILY
* REGION, BILLING_ENTITY
* RESERVATION_ID
* SAVINGS_PLANS_TYPE
* SAVINGS_PLAN_ARN
* OPERATING_SYSTEM


## AWS Account Configuration (Both Methods)

By default, `AWS_PROFILE` and `AWS_REGION` default to `default` and `us-east-1`. These values can be changed by modifying environment variables. The system attempts to retrieve sensible defaults for your AWS account using boto3 to determine your AWS account alias or ID.

**Serverless Framework:**
```bash
AWS_PROFILE="default" AWS_REGION="eu-west-1" serverless deploy \
    --param "slack_url=https://hooks.slack.com/services/xxx/yyy/zzzz" \
    --param "aws_account=my custom account name"
```

**AWS SAM:**
```bash
AWS_PROFILE="default" AWS_REGION="eu-west-1" sam deploy --parameter-overrides \
    SlackWebhookUrl="https://hooks.slack.com/services/xxx/yyy/zzzz" \
    AwsAccountName="my custom account name"
```

## Support for Different Cost Aggregations (Both Methods)

By default we show the unblended costs, but you can change the cost aggregation method AWS uses.

**Available values:** AmortizedCost, BlendedCost, NetAmortizedCost, NetUnblendedCost, NormalizedUsageAmount, UnblendedCost, and UsageQuantity.

More information is available [at the Metrics request parameter here](https://docs.aws.amazon.com/aws-cost-management/latest/APIReference/API_GetCostAndUsage.html)

**Serverless Framework:** Set the `COST_AGGREGATION` environment variable
**AWS SAM:** Use the `CostAggregation` parameter

## Project Structure

```
├── handler.py              # Main Lambda function code
├── serverless.yml          # Serverless Framework configuration
├── template.yaml           # AWS SAM template
├── requirements.txt        # Python dependencies (for SAM)
├── samconfig.toml          # SAM configuration file
├── package.json            # Node.js dependencies (for Serverless)
├── Pipfile                 # Python dependencies (for Serverless)
└── README.md              # This file
```

## Authors

- [Alex Ley](https://github.com/Alex-ley)
- [Enrico Stahn](https://github.com/estahn)
- [Ian Dees](https://github.com/iandees)
- [Regis Wilson](https://github.com/rwilson-release)
- [Rui Pinho](https://github.com/ruiseek)
- [Tamas Flamich](https://github.com/tamasflamich)
