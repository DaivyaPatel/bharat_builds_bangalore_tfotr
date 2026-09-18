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

Below is the state machine execution graph for the core backend pipeline, detailing the Map state and the resilient Catch blocks for each execution phase.

```mermaid
flowchart TD
    classDef aws fill:#FF9900,stroke:#232F3E,stroke-width:2px,color:#232F3E;
    classDef fail fill:#D13212,stroke:#fff,stroke-width:2px,color:#fff;
    
    Start((Start)) --> MapEnv
    
    subgraph MapEnv [Map state: MapEnvironments]
        direction TD
        RunCollector[AWS Lambda: Invoke<br><b>RunCollector</b>]:::aws
        RunDiff[AWS Lambda: Invoke<br><b>RunDiff</b>]:::aws
        RunAttribute[AWS Lambda: Invoke<br><b>RunAttribute</b>]:::aws
        RunPersist[AWS Lambda: Invoke<br><b>RunPersist</b>]:::aws
        FailStage[Fail state<br><b>FailStage</b>]:::fail
        
        RunCollector --> RunDiff
        RunDiff --> RunAttribute
        RunAttribute --> RunPersist
        RunPersist --> MapEnd(( ))
        
        RunCollector -->|Catch #1| FailStage
        RunDiff -->|Catch #1| FailStage
        RunAttribute -->|Catch #1| FailStage
        RunPersist -->|Catch #1| FailStage
        
        FailStage --> MapEnd
    end
    
    MapEnv --> EndNode((End))
```

## Getting Started

1. Deploy the backend via the automated setup scripts.
2. Ensure CloudTrail is logging management events to S3.
3. Start the EventBridge Scheduler rule to run the Step Functions pipeline.
