# API reference

This section documents the public Python API exported by Astro.

## Package exports

The following symbols are available from the top-level `astro` package:

| Symbol | Description |
|--------|-------------|
| `Pipeline` | Base class for pipeline definitions |
| `AstroFileSpec` | Declarative per-file configuration |
| `AstroFile` | Runtime file wrapper during `astro run` |
| `StepContext` | Execution context passed to step functions |
| `CanonicalIdResolver` | Stable UUID mapping and change detection |
| `FilterFn` | Type alias for filter step functions |
| `StatisticsRecorder` | Run, file, and step statistics |
| `StatScope` | Statistics scope enum |

## Pipeline

```{eval-rst}
.. automodule:: astro.pipeline.base
   :members: Pipeline
   :undoc-members:
   :show-inheritance:
   :no-index:
```

## Configuration models

```{eval-rst}
.. automodule:: astro.pipeline.models
   :members: IngestFileSpec, ExecutionMode, StepExecutionMode
   :undoc-members:
   :show-inheritance:
   :no-index:
```

## File containers

```{eval-rst}
.. automodule:: astro.pipeline.files
   :members: AstroFileSpec, AstroFile
   :undoc-members:
   :show-inheritance:
   :no-index:
```

## Step context

```{eval-rst}
.. automodule:: astro.pipeline.steps
   :members: StepContext, StepFn
   :undoc-members:
   :show-inheritance:
   :no-index:
```

## Filter types

```{eval-rst}
.. automodule:: astro.filter.types
   :members: FilterFn
   :undoc-members:
   :show-inheritance:
   :no-index:
```

## Statistics

```{eval-rst}
.. automodule:: astro.stats.recorder
   :members: StatisticsRecorder
   :undoc-members:
   :show-inheritance:
   :no-index:

.. automodule:: astro.stats.models
   :members: StatScope
   :undoc-members:
   :show-inheritance:
   :no-index:
```

## Canonical ID resolver

```{eval-rst}
.. automodule:: astro.resolver.resolver
   :members: CanonicalIdResolver
   :undoc-members:
   :show-inheritance:
   :no-index:
```
