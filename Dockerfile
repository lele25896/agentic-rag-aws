FROM public.ecr.aws/lambda/python:3.12
# no torch/sentence-transformers: embeddings come from Bedrock Titan on AWS
RUN pip install --no-cache-dir langgraph langgraph-checkpoint-aws langchain-core langchain-community \
    langchain-text-splitters langchain-aws faiss-cpu pymupdf pydantic ddgs boto3
COPY src/agent ${LAMBDA_TASK_ROOT}/agent
COPY data/*.pdf ${LAMBDA_TASK_ROOT}/data/
COPY index/bedrock ${LAMBDA_TASK_ROOT}/index/bedrock
CMD ["agent.handler.handler"]
