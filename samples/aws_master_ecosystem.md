# Exhaustive AWS Master Ecosystem

## Compute
- Amazon EC2
  - Over 500 instance types and instance families
  - Dedicated hardware options and license requirements
  - Common use cases: Lift and shift migrations, monolithic applications, hybrid environments
- AWS Lambda
  - Serverless compute service that automatically manages underlying resources
  - Common use cases: Microservices, event-driven applications
- Amazon ECS and EKS
  - Consistent container environments with easy deployment and scalability
  - Common use cases: Microservices, hybrid environments
- AWS Elastic Beanstalk
  - Managed application deployment service
- Amazon Lightsail
  - Simplified VPS hosting with preconfigured application stacks
  - Common use cases: Simple web applications, custom websites
- AWS Batch
  - Efficiently provisions and scales compute resources for jobs
  - Common use cases: High-Performance Computing, train ML models
- AWS Outposts
  - Hybrid cloud infrastructure extending AWS hardware on-premises

## Storage
- Amazon S3
  - Unlimited scalability, high availability, and multiple access options
  - Features: Transfer Acceleration and Access Points
- Amazon EBS
  - Scalable high-performance block-storage designed for EC2
  - Includes SSD-backed and HDD-backed storage options
- Amazon EFS
  - Serverless, fully elastic network file system supporting NFSv4
  - Automatically grows and shrinks across multiple compute solutions
- Amazon FSx
  - Managed file storage supporting NetApp ONTAP, OpenZFS, Windows File Server, and Lustre
- Amazon Glacier
  - Secure and cost-effective data archiving storage class
- AWS Backup
  - Centralized, policy-based data protection service
- AWS Storage Gateway
  - Hybrid storage integration service

## Databases
- Amazon RDS
  - Managed relational database supporting MySQL, PostgreSQL, Oracle, SQL Server, and MariaDB
  - Automates administrative overhead, backups, and Multi-AZ replication
- Amazon Aurora
  - Cloud-native, high-performance relational database engine compatible with MySQL and PostgreSQL
  - Features Aurora Serverless v2 for dynamic compute scaling
- Amazon DynamoDB
  - Fully managed, serverless NoSQL key-value and document database
  - Engineered to provide single-digit millisecond latency at any scale
- Amazon Redshift
  - Fully managed petabyte-scale cloud data warehouse optimized for OLAP
- Amazon DocumentDB
  - MongoDB-compatible JSON document database with decoupled compute and storage
- Amazon Neptune
  - Fast, reliable graph database engine optimized for highly connected datasets

## Networking and Content Delivery
- Amazon VPC
  - Logically isolated virtual network with public/private subnets and VPC Flow Logs
- AWS Direct Connect
  - Dedicated physical network link bypassing the public internet
- Amazon CloudFront
  - Global Content Delivery Network with edge locations and serverless edge compute
- AWS Global Accelerator
  - Network-layer service using static Anycast IP addresses and private backbone
- AWS Transit Gateway
  - Centralized regional transit hub for multi-VPC and hybrid interconnectivity
- Amazon Route 53
  - Highly available cloud DNS web service with latency-based routing and health checks
- AWS Site-to-Site VPN
  - IPsec-encrypted virtual private network connection over standard internet

## Analytics
- Amazon Athena
  - Serverless, interactive query service to analyze S3 data using SQL
- Amazon EMR
  - Managed big data platform for Apache Spark and Hadoop
- Amazon Kinesis
  - Real-time streaming data ingestion and processing platform
- AWS Glue
  - Serverless data integration and ETL service with Glue Data Catalog
- Amazon QuickSight
  - Business intelligence dashboards service

## Artificial Intelligence & Machine Learning
- Amazon SageMaker
  - Fully managed platform for building, training, and deploying ML models
- Amazon Bedrock
  - Managed service offering generative AI foundation models via a unified API
- Amazon Comprehend
  - Pre-trained Natural Language Processing service for unstructured text analysis
- Amazon Rekognition
  - Computer vision service for comprehensive image and video analysis
- Amazon Polly
  - Text-to-speech service
- Amazon Lex
  - Conversational bots service for building interactive voice and chat interfaces

## Security & Identity
- AWS IAM
  - Central identity and access management using roles, users, and JSON policies
- AWS KMS
  - Key management service for creating and controlling encryption keys
- AWS Secrets Manager
  - Secure storage and automated rotation for credentials and API keys
- AWS Shield
  - Managed DDoS protection service with Standard and Advanced tiers
- AWS WAF
  - Layer 7 web application firewall to block common exploits
- Amazon GuardDuty
  - Intelligent threat detection service analyzing logs and telemetry
- Amazon Inspector
  - Automated vulnerability management service scanning workloads and code
- AWS Security Hub
  - Centralized security posture management service

## Management & Governance
- AWS Organizations
  - Multi-account governance, consolidated billing, and SCP guardrails
- AWS Control Tower
  - Orchestration service for automated landing zones and pre-packaged guardrails
- AWS Config
  - Continuous configuration monitoring and compliance auditing
- Amazon CloudWatch
  - Observability platform for metrics, logs, dashboards, and alarms
- AWS CloudTrail
  - Auditing service recording API activity and user actions
- AWS Systems Manager
  - Operations hub for patch management, automation, and secure instance access
- AWS Service Catalog
  - Catalog management for approved IT service portfolios and templates

## Developer Tools <!-- fold -->
- AWS CodePipeline
  - Continuous delivery service that automates release pipelines
- AWS CodeBuild
  - Fully managed build service that compiles code and runs tests
- AWS CodeDeploy
  - Automates application deployments to EC2, Lambda, ECS and on-premises servers
- AWS CDK
  - Define cloud infrastructure in familiar programming languages
- AWS X-Ray
  - Distributed tracing to analyse and debug applications

## IoT
- AWS IoT Core
  - Managed service for secure device connectivity, MQTT protocols, and digital twins
- AWS IoT Greengrass
  - Edge runtime and local computing for devices
- AWS IoT SiteWise
  - Industrial IoT analytics service
- AWS IoT Device Defender
  - Security management service for IoT devices

## Business Applications & End User Computing
- Amazon WorkSpaces
  - Managed Desktop-as-a-Service virtual Windows or Linux desktop solution
- Amazon Connect
  - Omnichannel cloud contact center service with built-in AI capabilities
- Amazon Chime
  - Enterprise communications, video conferencing, and WebRTC SDK
- Amazon WorkDocs
  - Managed enterprise document management and collaboration service

## Migration & Modernization
- AWS Application Migration Service
  - Primary service for lift-and-shift server migrations with continuous replication
- AWS Database Migration Service
  - Secure migration of relational and NoSQL databases with minimal downtime
- AWS Migration Hub
  - Centralized dashboard for tracking migration progress across tools
- AWS Snow Family
  - Rugged physical edge computing and data transfer appliances

## AWS Elemental Media Services
- AWS Elemental MediaLive
  - Broadcast-grade, real-time live video encoding engine with ABR support
- AWS Elemental MediaConvert
  - File-based video transcoding service for on-demand media library processing
- AWS Elemental MediaPackage <!-- fold -->
  - Just-in-time video packaging and origination for HLS, DASH and CMAF
- AWS Elemental MediaTailor <!-- fold -->
  - Server-side ad insertion and channel assembly for personalised streams
- AWS Elemental MediaStore <!-- fold -->
  - Storage optimised for live and on-demand media origin
