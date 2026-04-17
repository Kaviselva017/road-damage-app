import sentry_sdk
import logging

logger = logging.getLogger(__name__)

def capture_ai_error(complaint_id: str, error: Exception, model_input_shape: str = "unknown"):
    """
    Capture AI inference errors and send structured context to Sentry.
    """
    logger.error(f"AI Inference error on complaint {complaint_id}: {error}", exc_info=True)
    with sentry_sdk.push_scope() as scope:
        scope.set_tag("complaint_id", complaint_id)
        scope.set_context("ai_inference", {
            "model_input_shape": model_input_shape,
            "error_type": type(error).__name__
        })
        sentry_sdk.capture_exception(error)
