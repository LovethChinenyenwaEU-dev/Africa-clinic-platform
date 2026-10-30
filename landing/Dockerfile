# The public AfriPeak Health landing page: its own small Next.js app, kept exactly as
# designed (Next 14, Tailwind 3, DaisyUI 4), separate from the clinic app on port 3000.
FROM node:22-alpine

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

EXPOSE 3000
CMD ["npx", "next", "dev", "-H", "0.0.0.0", "-p", "3000"]
