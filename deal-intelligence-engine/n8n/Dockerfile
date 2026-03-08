FROM n8nio/n8n:2.9.4
# Install adm-zip for PPTX text extraction in Code nodes
USER root
RUN mkdir -p /opt/custom-nodes && cd /opt/custom-nodes && npm init -y && npm install adm-zip && chown -R node:node /opt/custom-nodes
USER node
ENV NODE_PATH=/opt/custom-nodes/node_modules:/usr/local/lib/node_modules
