FROM python:3.11-slim

# install curl, xz-utils for ffmpeg download, and git for pip
RUN apt-get update && apt-get install -y --no-install-recommends curl xz-utils git \
    && rm -rf /var/lib/apt/lists/*

# install ffmpeg
RUN curl https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz > /tmp/ffmpeg-release.tar.xz \
    && tar xvf /tmp/ffmpeg-release.tar.xz -C /opt \
    && mv /opt/ffmpeg-* /opt/ffmpeg \
    && cd /opt/ffmpeg \
    && mv model /usr/local/share \
    && mv ffmpeg ffprobe qt-faststart /usr/local/bin \
    && rm /tmp/ffmpeg-release.tar.xz

# set working directory
WORKDIR /app

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copy the rest of the application
COPY ebustl_utils /app/ebustl_utils
