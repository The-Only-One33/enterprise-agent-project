"""
可观测性配置 (OpenTelemetry)
"""
from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter


def setup_observability(app: FastAPI):
    """配置可观测性"""
    
    # 资源
    resource = Resource.create({
        "service.name": "enterprise-agent",
        "service.version": "1.0.0",
    })
    
    # Tracer Provider
    provider = TracerProvider(resource=resource)
    
    # 控制台导出器 (开发环境)
    console_exporter = ConsoleSpanExporter()
    provider.add_span_processor(BatchSpanProcessor(console_exporter))
    
    trace.set_tracer_provider(provider)
    
    # FastAPI 自动instrument
    FastAPIInstrumentor.instrument_app(app)


def get_tracer(name: str):
    """获取Tracer"""
    return trace.get_tracer(name)
