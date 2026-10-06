# Amazon Web Services Well-Architected Framework

## Operational Excellence
- Focus
  - Running and monitoring systems effectively
  - Gaining visibility into operation
  - Continuously refining processes and procedures
- Core Design Principles
  - Perform operations as code (Amazon Web Services CloudFormation or Cloud Development Kit)
  - Make frequent, small, reversible changes
  - Anticipate and learn from failures
- Key Amazon Web Services Services
  - Amazon Web Services CloudFormation
  - Amazon Web Services Systems Manager
  - Amazon CloudWatch
  - Amazon Web Services Config
- Pillar Metrics and Anti-Patterns
  - Primary Metric: Mean Time to Recovery
  - Anti-Pattern: Manual command-line interface changes to production servers

## Security
- Focus
  - Protecting data, identities, systems, and cloud assets
  - Enhancing compliance and posture
- Core Design Principles
  - Strong identity foundation (least privilege, centralized identities, mandatory multi-factor authentication)
  - Traceability and auditability
  - Defense in depth
  - Protect data in transit and at rest
- Key Amazon Web Services Services
  - Amazon Web Services Identity and Access Management
  - Amazon Web Services Key Management Service
  - Amazon Web Services WAF
  - Amazon Web Services Shield
  - Amazon GuardDuty
  - Amazon Inspector
- Pillar Metrics and Anti-Patterns
  - Primary Metric: Zero unauthorized access
  - Anti-Pattern: Hardcoding root credentials or open public Simple Storage Service buckets

## Reliability
- Focus
  - Ensuring workloads perform consistently
  - Recovering smoothly from infrastructure disruptions
  - Dynamically acquiring computing capacity
- Core Design Principles
  - Automatically recover from failure
  - Test recovery procedures
  - Scale horizontally to increase resilience
- Key Amazon Web Services Services
  - Amazon Route 53
  - Auto Scaling
  - Elastic Load Balancing
  - Amazon Simple Storage Service multi-Availability Zone snapshots
  - Amazon Web Services Backup
- Pillar Metrics and Anti-Patterns
  - Primary Metric: Recovery Time Objective and Recovery Point Objective
  - Anti-Pattern: Single-point-of-failure monolithic server in one Availability Zone

## Performance Efficiency
- Focus
  - Using computing resources efficiently
  - Maintaining efficiency as demand evolves
- Core Design Principles
  - Democratize advanced technologies
  - Go global in minutes
  - Experiment more often
- Key Amazon Web Services Services
  - Amazon Web Services Graviton
  - Amazon Web Services Fargate
  - Amazon ElastiCache
  - Amazon CloudFront
  - Amazon Web Services Global Accelerator
- Pillar Metrics and Anti-Patterns
  - Primary Metric: Request latency and throughput
  - Anti-Pattern: Over-provisioned static instances

## Cost Optimization
- Focus
  - Running cloud systems to deliver maximum business value
  - Achieving the lowest possible price point
- Core Design Principles
  - Adopt a consumption model
  - Measure overall efficiency
  - Stop spending money on undifferentiated heavy lifting
- Key Amazon Web Services Services
  - Amazon Web Services Cost Explorer
  - Amazon Web Services Budgets
  - Amazon Web Services Compute Optimizer
  - Amazon Elastic Compute Cloud Spot Instances
  - Savings Plans
- Pillar Metrics and Anti-Patterns
  - Primary Metric: Cost per transaction
  - Anti-Pattern: Running unattached Elastic Block Store volumes

## Sustainability
- Focus
  - Minimizing environmental and carbon footprint
  - Maximizing resource utilization
- Core Design Principles
  - Understand your impact
  - Maximize utilization
  - Adopt efficient hardware and software
- Key Amazon Web Services Services
  - Amazon Web Services Customer Carbon Footprint Tool
  - Amazon Web Services Graviton
  - Amazon Web Services Lambda
  - Amazon Simple Storage Service Intelligent-Tiering
- Pillar Metrics and Anti-Patterns
  - Primary Metric: Carbon emissions per business transaction
  - Anti-Pattern: Storing stale logs indefinitely

## Real-World Use Cases
- Multi-Tier E-Commerce Platform Modernization
  - Scenario: Black Friday shopping spikes and monolithic database lag
  - Implementation: Amazon Elastic Container Service on Amazon Web Services Fargate
  - Implementation: Amazon Aurora Multi-Availability Zone database with read replicas
  - Implementation: Amazon ElastiCache and Amazon CloudFront
- Automated Cloud Compliance and Threat Defense
  - Scenario: Fintech startup needing security certifications
  - Implementation: Amazon Web Services Control Tower and Amazon Web Services Organizations
  - Implementation: Amazon Web Services Cloud Development Kit and Identity and Access Management
  - Implementation: Amazon GuardDuty and Amazon CloudWatch
- Data Lake Optimization and Green Computing
  - Scenario: Spiraling storage bills and high energy consumption
  - Implementation: Amazon Web Services Graviton-powered instances
  - Implementation: Amazon Simple Storage Service Intelligent-Tiering and Glacier Deep Archive
