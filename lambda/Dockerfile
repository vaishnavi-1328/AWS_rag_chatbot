FROM public.ecr.aws/lambda/python:3.11

# Install dependencies
COPY requirements-docker.txt ${LAMBDA_TASK_ROOT}/
RUN pip install -r ${LAMBDA_TASK_ROOT}/requirements-docker.txt --target "${LAMBDA_TASK_ROOT}"

# Copy source code
COPY handler.py ${LAMBDA_TASK_ROOT}/
COPY src/ ${LAMBDA_TASK_ROOT}/src/

# Set the handler
CMD [ "handler.lambda_handler" ]
