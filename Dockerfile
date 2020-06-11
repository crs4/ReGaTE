
FROM python:alpine3.12 AS build

RUN apk add --no-cache \
  bash \
  gcc \
  libxslt-dev \
  py3-pip \
  musl-dev


COPY requirements.txt /tmp/requirements.txt

RUN pip3 install --no-cache-dir -r /tmp/requirements.txt

RUN mkdir /tmp/regate/
COPY ./ /tmp/regate/
RUN cd /tmp/regate && python setup.py install



FROM python:alpine3.12

RUN apk add --no-cache \
  bash \
  libxslt \
  py3-pip

COPY --from=build /usr/local/lib/python3.8/ /usr/local/lib/python3.8/
COPY --from=build /usr/local/bin/regate /usr/local/bin/

RUN addgroup regate && adduser -G regate -h /regate -D regate
USER regate
WORKDIR /regate
ENTRYPOINT [ "/usr/local/bin/regate" ]

