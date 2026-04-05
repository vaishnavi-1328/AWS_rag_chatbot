# NHTSA Recall & TSB Analyzer

A professional-grade RAG system that helps automotive technicians and engineers find relevant Technical Service Bulletins (TSBs), recalls, and complaints for specific vehicle issues.

## Features

- **Natural Language Queries**: Ask questions like "2019 Ford F-150 engine stalls at low speed"
- **Multi-Source Search**: Searches recalls, complaints, and TSBs simultaneously
- **LangGraph Orchestration**: Multi-agent workflow with routing, grading, and hallucination checking
- **AWS Bedrock Integration**: Uses Claude 3 Haiku for generation and Titan for embeddings
- **Serverless Deployment**: Lambda + API Gateway for scalable, cost-effective hosting

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Streamlit UI (EC2 + Nginx)                               │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       API Gateway (REST)                                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     AWS Lambda (LangGraph)                                   │
│   Vehicle Parser → Router → Retriever → Grader → Generator → Hallucination  │
└─────────────────────────────────────────────────────────────────────────────┘
                    │                              │
                    ▼                              ▼
         ┌──────────────────┐          ┌────────────────────┐
         │   AWS Bedrock    │          │      AWS S3        │
         │ Claude 3 Haiku   │          │  FAISS Index +     │
         │ Titan Embeddings │          │  Document Data     │
         └──────────────────┘          └────────────────────┘
```

## Quick Start

### Prerequisites

- Python 3.11+
- AWS Account with Bedrock access
- AWS CLI configured

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/nhtsa-recall-analyzer.git
cd nhtsa-recall-analyzer

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env
# Edit .env with your AWS credentials
```

### Data Preparation

```bash
# Option 1: Create sample data (no API calls)
python scripts/fetch_nhtsa_data.py --sample-only

# Option 2: Fetch real NHTSA data (takes time)
python scripts/fetch_nhtsa_data.py --makes Ford,Toyota --start-year 2019 --end-year 2024

# Process data
python scripts/process_data.py

# Build FAISS index
python scripts/build_index.py --mock  # Use --mock for testing without Bedrock
```

### Local Testing

```bash
# Run the workflow directly
python -m src.graph.workflow "2019 Ford F-150 engine stalls"

# Run Streamlit frontend
cd frontend
streamlit run app.py
```

## Project Structure

```
nhtsa-recall-analyzer/
├── src/
│   ├── agents/          # LangGraph agent implementations
│   │   ├── vehicle_parser.py
│   │   ├── router.py
│   │   ├── retriever.py
│   │   ├── grader.py
│   │   ├── generator.py
│   │   └── hallucination.py
│   ├── graph/           # LangGraph workflow
│   │   ├── state.py     # State schema
│   │   └── workflow.py  # Main graph
│   ├── retrieval/       # Vector store
│   └── utils/           # Utilities
├── lambda/              # AWS Lambda
├── frontend/            # Streamlit UI
├── scripts/             # Setup scripts
└── data/                # Data files
```

## AWS Deployment

### 1. Enable Bedrock Models

In AWS Console → Bedrock → Model access:
- Enable `Claude 3 Haiku`
- Enable `Titan Text Embeddings v2`

### 2. Create S3 Bucket

```bash
aws s3 mb s3://nhtsa-recall-analyzer --region us-east-1
```

### 3. Upload Index

```bash
python scripts/upload_to_s3.py
```

### 4. Deploy Lambda

```bash
cd lambda
./package_lambda.sh
# Upload via AWS Console or CLI
```

### 5. Set up API Gateway

Create REST API with POST /query endpoint pointing to Lambda.

### 6. Deploy Streamlit to EC2

```bash
# SSH to EC2 instance
ssh -i your-key.pem ec2-user@your-ec2-ip

# Run setup script
./scripts/ec2_setup.sh
```

## Cost Estimate

| Service | Monthly Cost (Light Usage) |
|---------|---------------------------|
| Lambda | $0 (Free tier) |
| EC2 t2.micro | $0 (Free tier) |
| S3 | $0 (Free tier) |
| API Gateway | $0 (Free tier) |
| **Bedrock** | **~$1-2** |
| **Total** | **~$1-2/month** |

## Example Queries

1. `"2019 Ford F-150 3.5L EcoBoost - engine stalls at low speed"`
2. `"Any recalls for 2020 Toyota Camry?"`
3. `"2018 Honda CR-V oil dilution issue"`
4. `"Chevy Silverado transmission shudder"`

## Development

### Running Tests

```bash
pytest tests/
```

### Code Formatting

```bash
black src/ scripts/ lambda/ frontend/
ruff check src/ scripts/ lambda/ frontend/
```

## License

MIT License

## Acknowledgments

- Data provided by [NHTSA](https://www.nhtsa.gov)
- Built with [LangGraph](https://github.com/langchain-ai/langgraph) and [AWS Bedrock](https://aws.amazon.com/bedrock/)
