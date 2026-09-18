# DriftLens

DriftLens is an automated configuration drift detection and attribution platform built for AWS. It captures point-in-time snapshots of AWS resources across environments, detects configuration drift, and traces the drift back to the exact CloudTrail event that caused it.

## Architecture

```mermaid
flowchart TD
    %% Define styles
    classDef aws fill:#FF9900,stroke:#232F3E,stroke-width:2px,color:#232F3E;
    
    %% Triggers
    Scheduler[Amazon EventBridge\nScheduler]:::aws
    
    %% Pipeline
    subgraph StepFunctions [AWS Step Functions Pipeline]
        Collector[Collector Lambda\nExtracts Configs]:::aws
        Diff[Diff Lambda\nCompares Snapshots]:::aws
        Attribution[Attribution Lambda\nFinds CloudTrail Events]:::aws
        Persist[Persist Lambda\nSaves to DB]:::aws
        
        Collector --> Diff --> Attribution --> Persist
    end
    
    %% Data Stores
    S3[(Amazon S3\nSnapshots)]:::aws
    Dynamo[(Amazon DynamoDB\nDrift Records)]:::aws
    Athena[(Amazon Athena\nCloudTrail Queries)]:::aws
    CloudTrail[AWS CloudTrail\nAudit Logs]:::aws
    
    %% Product / API
    API[Amazon API Gateway\nREST API]:::aws
    APILambda[API Lambda\nServes React App]:::aws
    Bedrock[Amazon Bedrock\nAI Explanations]:::aws
    UI[React Dashboard\nAmplify Hosting]:::aws
    
    %% Connections
    Scheduler -->|Triggers Hourly| StepFunctions
    
    Collector -->|Writes & Reads| S3
    Attribution -->|Queries| Athena
    Athena -->|Reads| CloudTrail
    Persist -->|Writes| Dynamo
    
    UI -->|Calls| API
    API -->|Triggers| APILambda
    APILambda -->|Reads| Dynamo
    APILambda -->|Queries| Bedrock
```

### Step Functions Pipeline Graph
*(Please replace this placeholder with the `step-functions-graph.png` screenshot from DL-014)*

![Step Functions Graph](step-functions-graph.png)

## Getting Started

1. Deploy the backend via the automated setup scripts.
2. Ensure CloudTrail is logging management events to S3.
3. Start the EventBridge Scheduler rule to run the Step Functions pipeline.
