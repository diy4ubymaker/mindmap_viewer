# Amazon Web Services Cloud Ecosystem

## Compute and Containers
- Amazon Elastic Compute Cloud
  - Summary: Resizable virtual machines providing scalable compute capacity in the cloud
  - Use Case: Hosting monolithic legacy web applications requiring full control
  - Use Case: Running high-performance computing simulations and batch data pipelines
- AWS Lambda
  - Summary: Serverless event-driven compute engine running code without server management
  - Use Case: Automatically generating image thumbnails on media upload
  - Use Case: Serving lightweight backend APIs triggered by Amazon API Gateway
- Amazon Elastic Container Service and Amazon Elastic Kubernetes Service
  - Summary: Managed container orchestration via native task definitions or upstream Kubernetes
  - Use Case: Deploying microservices architectures with automated scaling
  - Use Case: Migrating on-premise clusters seamlessly to a managed control plane
- AWS Fargate
  - Summary: Serverless compute engine for containers operating without node management
  - Use Case: Running sporadic containerized data transformation tasks
  - Use Case: Deploying web microservices without patching host operating systems

## Storage
- Amazon Simple Storage Service
  - Summary: Highly durable and scalable object storage designed for any data volume
  - Use Case: Serving static website assets with content delivery network distribution
  - Use Case: Storing enterprise data lakes for analytical querying
- Amazon Elastic Block Store
  - Summary: High-performance persistent block storage volumes for compute instances
  - Use Case: Hosting primary boot drives and operating system files
  - Use Case: Running transactional database workloads needing low latency
- Amazon Elastic File System
  - Summary: Scalable fully managed shared file system accessible concurrently
  - Use Case: Providing shared storage across web-server content management fleets
  - Use Case: Supplying shared home directories for machine learning training
- Amazon Simple Storage Service Glacier
  - Summary: Low-cost secure cloud storage classes tailored for cold archiving
  - Use Case: Retaining multi-year financial audit logs and compliance data
  - Use Case: Storing legacy medical image archives requiring long retention

## Database
- Amazon Relational Database Service and Amazon Aurora
  - Summary: Managed relational databases supporting multiple engines and Aurora
  - Use Case: Supporting e-commerce order processing with transactional consistency
  - Use Case: Running financial transaction ledgers with automated failover
- Amazon DynamoDB
  - Summary: Fully managed serverless NoSQL key-value and document database
  - Use Case: Storing user session states, preferences, and shopping carts
  - Use Case: Real-time mobile gaming leaderboards handling concurrent reads
- Amazon ElastiCache
  - Summary: In-memory data store service supporting Redis and Memcached
  - Use Case: Caching frequent database queries to reduce backend load
  - Use Case: Handling real-time distributed session token validation
- Amazon DocumentDB and Amazon Keyspaces
  - Summary: Scalable managed database services compatible with MongoDB and Cassandra
  - Use Case: Migrating existing MongoDB document collections without driver changes
  - Use Case: Scaling wide-column Internet of Things time-series telemetry data

## Networking and Content Delivery
- Amazon Virtual Private Cloud
  - Summary: Isolated virtual network enabling secure resource provisioning
  - Use Case: Segmenting public load balancers from private backend tiers
  - Use Case: Establishing secure virtual private network tunnels to data centers
- Amazon CloudFront
  - Summary: Low-latency content delivery network globally delivering digital content
  - Use Case: Accelerating global distribution of static media files at edge locations
  - Use Case: Terminating security certificates and preventing distributed denial of service
- Elastic Load Balancing
  - Summary: Distributes incoming application and network traffic across targets
  - Use Case: Layer 7 path-based and host-based microservices routing
  - Use Case: Terminating extreme-throughput connections for gaming and trading
- Amazon Route 53
  - Summary: Highly available and scalable cloud Domain Name System web service
  - Use Case: Managing public domain registration and geo-proximity routing
  - Use Case: Configuring automated health-check failover during outages

## Security, Identity, and Compliance
- AWS Identity and Access Management
  - Summary: Securely manages user identities, credentials, and temporary permissions
  - Use Case: Assigning temporary roles to instances to eliminate hardcoded credentials
  - Use Case: Enforcing multi-factor authentication and least-privilege policies
- AWS Key Management Service and AWS CloudHSM
  - Summary: Centralized key creation and management service for data encryption
  - Use Case: Managing customer-managed encryption keys for storage and databases
  - Use Case: Storing cryptographic signing keys inside dedicated hardware modules
- AWS Web Application Firewall and AWS Shield
  - Summary: Application layer protection against web exploits and managed defenses
  - Use Case: Blocking automated web scrapers and credential-stuffing attacks
  - Use Case: Providing automated distributed denial of service mitigation
- Amazon Cognito
  - Summary: Customer identity and access management service for authentication
  - Use Case: Implementing social sign-in for mobile applications
  - Use Case: Managing a self-contained business-to-consumer customer directory

## Analytics and Big Data <!-- fold -->
- Amazon Athena
  - Summary: Serverless interactive query service for analyzing data in Amazon S3 with SQL
  - Use Case: Ad-hoc querying of application and access logs without loading a database
- Amazon Kinesis
  - Summary: Real-time streaming data ingestion and processing platform
  - Use Case: Processing clickstream and telemetry events as they arrive
- AWS Glue
  - Summary: Serverless data integration and ETL service with a central Data Catalog
  - Use Case: Preparing and cataloging data lake datasets for analytics
- Amazon EMR
  - Summary: Managed big data platform for Apache Spark and Hadoop
  - Use Case: Running large-scale batch transformations and machine learning feature pipelines

## Artificial Intelligence and Machine Learning
- Amazon SageMaker
  - Summary: Comprehensive managed platform to build, train, and deploy models
  - Use Case: Training deep neural networks on distributed graphics processing units
  - Use Case: Deploying real-time inference endpoints with auto-scaling
- Amazon Bedrock
  - Summary: Managed service offering access to top foundation models via API
  - Use Case: Building enterprise retrieval-augmented generation assistants
  - Use Case: Generating tailored marketing copy and internal summarizations
- AWS Pre-trained Artificial Intelligence Services
  - Summary: Ready-to-use computer vision and natural language processing APIs
  - Use Case: Moderating user-uploaded photos and videos for explicit content
  - Use Case: Transcribing call-center recordings and analyzing sentiment

## Management, Governance, and Observability
- Amazon CloudWatch
  - Summary: Central monitoring and observability service collecting metrics and logs
  - Use Case: Triggering auto-scaling actions based on resource utilization alarms
  - Use Case: Centralizing application log streams and alerting on error spikes
- AWS CloudTrail
  - Summary: Governance service recording API calls and account activity
  - Use Case: Tracking administrative actions for security audits
  - Use Case: Fulfilling regulatory compliance requirements via audit histories
- AWS CloudFormation
  - Summary: Infrastructure as Code tool allowing declarative resource provisioning
  - Use Case: Spinning up consistent environments using version-controlled templates
  - Use Case: Automating multi-region disaster recovery deployments

## Application Integration and Messaging
- Amazon Simple Queue Service
  - Summary: Fully managed message queuing service for decoupling microservices
  - Use Case: Buffering video encoding jobs to allow asynchronous worker pools
  - Use Case: Decoupling checkout tiers from payment processing systems
- Amazon Simple Notification Service
  - Summary: Fully managed publish and subscribe messaging service enabling fan-out
  - Use Case: Broadcasting critical system alerts simultaneously via multiple endpoints
  - Use Case: Publishing order events to multiple decoupled downstream queues
- Amazon EventBridge
  - Summary: Serverless event bus connecting applications using data from sources
  - Use Case: Triggering security remediation workflows upon unauthorized key creation
  - Use Case: Ingesting external webhooks from third-party tools to drive tasks

## Developer Tools and Continuous Integration and Continuous Delivery
- AWS CodePipeline, AWS CodeBuild, and AWS CodeDeploy
  - Summary: Continuous integration and continuous delivery toolchain for software releases
  - Use Case: Automating compilation, unit testing, and container image creation
  - Use Case: Executing rolling and blue-green deployments with automated rollback

## Migration and Hybrid Cloud
- AWS Direct Connect
  - Summary: Dedicated private network connection linking data centers to the cloud
  - Use Case: Bypassing public internet routing for database synchronization
  - Use Case: Connecting corporate networks securely to private virtual cloud subnets
- AWS Snow Family
  - Summary: Physical ruggedized hardware appliances to transfer massive data volumes
  - Use Case: Migrating multi-terabyte tape backup archives in constrained bandwidth
  - Use Case: Collecting and preprocessing sensor data in remote edge environments
