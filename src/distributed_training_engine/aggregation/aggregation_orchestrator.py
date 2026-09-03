"""
Aggregation orchestrator workflow coordinator.
"""

from __future__ import annotations
import logging
from typing import Optional, Union
from ..model_type import ModelType
from .aggregation_request import AggregationRequest
from .aggregation_result import AggregationResult
from .aggregator_adapter import AggregatorAdapter
from .aggregator_adapter_registery import AggregatorAdapterRegistery
from .exceptions import InvalidAggregationRequestError

logger = logging.getLogger("distributed_training_engine.aggregation.orchestrator")


class AggregationOrchestrator:
    """
    Coordinates the lifecycle of model delta aggregation.
    Resolves the model-specific AggregatorAdapter through AggregatorAdapterRegistry
    and drives the sequential aggregation lifecycle.
    """

    def __init__(
        self,
        model_type: Optional[Union[ModelType, str]] = ModelType.CANONICAL_TORCH,
        request: Optional[AggregationRequest] = None,
    ) -> None:
        """
        Initialize the orchestrator.

        Args:
            model_type: Target ModelType enum or string (defaults to CANONICAL_TORCH).
            request: Optional AggregationRequest if pre-configuring the orchestrator.
        """
        self.model_type = ModelType(model_type) if isinstance(model_type, str) else model_type
        self.request = request

    def Aggregate(
        self,
        request: Optional[AggregationRequest] = None,
        model_type: Optional[Union[ModelType, str]] = None,
    ) -> AggregationResult:
        """
        Execute the complete aggregation lifecycle:
        1. Receive AggregationRequest.
        2. Resolve AggregatorAdapter using ModelType.
        3. Construct AggregatorAdapter(request).
        4. Invoke adapter.LoadDelta().
        5. Invoke adapter.ValidateDelta().
        6. Invoke adapter.Aggregate().
        7. Invoke adapter.CreateNewVersion().
        8. Return resulting AggregationResult.

        Args:
            request: The AggregationRequest containing model ID, versions, and update paths.
            model_type: Optional ModelType override.

        Returns:
            AggregationResult detailing the published model version.
        """
        active_request = request or self.request
        if active_request is None:
            raise InvalidAggregationRequestError("No AggregationRequest provided to orchestrator.")
        active_request.validate()

        effective_model_type = (
            ModelType(model_type) if isinstance(model_type, str) else (model_type or self.model_type)
        )
        if effective_model_type is None:
            effective_model_type = ModelType.CANONICAL_TORCH

        logger.info(
            "Starting aggregation lifecycle [model_id=%s, base_v=%d, new_v=%d, updates_count=%d, model_type=%s]",
            active_request.model_id,
            active_request.base_model_version,
            active_request.new_version,
            len(active_request.updates),
            effective_model_type,
        )

        # 1. Resolve adapter class via registry
        logger.debug("Resolving aggregator adapter for model type '%s'", effective_model_type)
        adapter_cls = AggregatorAdapterRegistery.Get(effective_model_type)
        logger.info("Resolved aggregator adapter: %s", adapter_cls.__name__)

        # 2. Construct adapter with request
        adapter: AggregatorAdapter = adapter_cls(active_request)

        # 3. Load deltas
        logger.info("Step 1/4: Loading delta artifacts...")
        adapter.LoadDelta()

        # 4. Validate deltas & target output
        logger.info("Step 2/4: Validating delta schemas and base model compatibility...")
        adapter.ValidateDelta()

        # 5. Perform Federated Averaging
        logger.info("Step 3/4: Performing sample-weighted Federated Averaging...")
        adapter.Aggregate()

        # 6. Create next model version
        logger.info("Step 4/4: Atomically publishing new model version...")
        result: AggregationResult = adapter.CreateNewVersion()

        logger.info(
            "Aggregation successfully completed! [new_version=%d, path=%s, updates_aggregated=%d]",
            result.new_model_version,
            result.model_path,
            result.updates_count,
        )
        return result

    # Aliases
    aggregate = Aggregate
    run = Aggregate
