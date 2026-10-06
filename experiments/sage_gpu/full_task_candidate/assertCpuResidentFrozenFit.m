function valid = assertCpuResidentFrozenFit(fit)
%ASSERTCPURESIDENTFROZENFIT Validate the Frozen fit schema and CPU residency.
% This boundary check does not modify values or perform scientific work.

assertNoGpuArrayRecursive(fit);

fitFields = { ...
    'windowId'; 'catalogIndex'; 'recordingTimeS'; 'towS'; ...
    'models'; 'selectedOrder'; 'errorMessage'};
if ~isstruct(fit) || ~isscalar(fit) || ...
        ~isequal(fieldnames(fit), fitFields)
    contractFailure('FIT_FIELDS_OR_SCALAR_SHAPE_MISMATCH');
end

assertDoubleScalar(fit.windowId, 'windowId');
assertDoubleScalar(fit.catalogIndex, 'catalogIndex');
assertDoubleScalar(fit.recordingTimeS, 'recordingTimeS');
assertDoubleScalar(fit.towS, 'towS');
assertDoubleScalar(fit.selectedOrder, 'selectedOrder');
if ~(isstring(fit.errorMessage) && isscalar(fit.errorMessage)) && ...
        ~(ischar(fit.errorMessage) && isrow(fit.errorMessage))
    contractFailure('FIT_ERROR_MESSAGE_TYPE_MISMATCH');
end

if ~iscell(fit.models) || numel(fit.models) ~= 4
    contractFailure('FIT_MODELS_MUST_CONTAIN_L1_THROUGH_L4');
end

modelFields = { ...
    'order'; 'paths'; 'rss'; 'bic'; 'valid'; 'relativePowerDb'; ...
    'minimumSeparationSamples'; 'minimumMultipathPowerDb'; ...
    'maximumRelativeDopplerHz'; 'maximumCoherence'; 'rssHistory'};
pathFields = {'delaySamples'; 'dopplerHz'; 'alpha'; 'score'};
for order = 1:4
    model = fit.models{order};
    if ~isstruct(model) || ~isscalar(model)
        contractFailure(sprintf('MODEL_L%d_MUST_BE_SCALAR_STRUCT', order));
    end
    actualModelFields = fieldnames(model);
    expectedWithError = [modelFields; {'errorMessage'}];
    if ~isequal(actualModelFields, modelFields) && ...
            ~isequal(actualModelFields, expectedWithError)
        contractFailure(sprintf('MODEL_L%d_FIELDS_MISMATCH', order));
    end

    assertDoubleScalar(model.order, sprintf('models{%d}.order', order));
    if model.order ~= order
        contractFailure(sprintf('MODEL_ORDER_INDEX_MISMATCH_L%d', order));
    end
    assertDoubleScalar(model.rss, sprintf('models{%d}.rss', order));
    assertDoubleScalar(model.bic, sprintf('models{%d}.bic', order));
    if ~islogical(model.valid) || ~isscalar(model.valid)
        contractFailure(sprintf('MODEL_VALIDITY_TYPE_MISMATCH_L%d', order));
    end
    assertDoubleArray(model.relativePowerDb, ...
        sprintf('models{%d}.relativePowerDb', order));
    if numel(model.relativePowerDb) ~= order
        contractFailure(sprintf('MODEL_RELATIVE_POWER_LENGTH_MISMATCH_L%d', order));
    end
    assertDoubleScalar(model.minimumSeparationSamples, ...
        sprintf('models{%d}.minimumSeparationSamples', order));
    assertDoubleScalar(model.minimumMultipathPowerDb, ...
        sprintf('models{%d}.minimumMultipathPowerDb', order));
    assertDoubleScalar(model.maximumRelativeDopplerHz, ...
        sprintf('models{%d}.maximumRelativeDopplerHz', order));
    assertDoubleScalar(model.maximumCoherence, ...
        sprintf('models{%d}.maximumCoherence', order));
    assertDoubleArray(model.rssHistory, ...
        sprintf('models{%d}.rssHistory', order));

    if isfield(model, 'errorMessage') && ...
            ~(isstring(model.errorMessage) && isscalar(model.errorMessage)) && ...
            ~(ischar(model.errorMessage) && isrow(model.errorMessage))
        contractFailure(sprintf('MODEL_ERROR_MESSAGE_TYPE_MISMATCH_L%d', order));
    end

    paths = model.paths;
    if isempty(paths)
        if model.valid
            contractFailure(sprintf('VALID_MODEL_HAS_NO_PATHS_L%d', order));
        end
        continue;
    end
    if ~isstruct(paths) || ~isequal(fieldnames(paths), pathFields) || ...
            numel(paths) ~= order
        contractFailure(sprintf('MODEL_PATH_SCHEMA_MISMATCH_L%d', order));
    end
    for pathIndex = 1:numel(paths)
        path = paths(pathIndex);
        assertDoubleScalar(path.delaySamples, ...
            sprintf('models{%d}.paths(%d).delaySamples', order, pathIndex));
        assertDoubleScalar(path.dopplerHz, ...
            sprintf('models{%d}.paths(%d).dopplerHz', order, pathIndex));
        assertDoubleScalar(path.alpha, ...
            sprintf('models{%d}.paths(%d).alpha', order, pathIndex));
        if ~isfinite(real(path.alpha)) || ~isfinite(imag(path.alpha))
            contractFailure(sprintf('PATH_ALPHA_NOT_FINITE_L%d_P%d', order, pathIndex));
        end
        assertDoubleScalar(path.score, ...
            sprintf('models{%d}.paths(%d).score', order, pathIndex));
    end
end

valid = true;
end

function assertNoGpuArrayRecursive(value)
if isa(value, 'gpuArray')
    error('FullTaskGpuCandidate:NO_GPUARRAY_IN_RETURNED_FIT', ...
        ['NO_GPUARRAY_IN_RETURNED_FIT: a gpuArray remains inside the fit ', ...
        'returned to the Frozen runStage2 controller.']);
elseif iscell(value)
    for index = 1:numel(value)
        assertNoGpuArrayRecursive(value{index});
    end
elseif isstruct(value)
    names = fieldnames(value);
    for elementIndex = 1:numel(value)
        for fieldIndex = 1:numel(names)
            assertNoGpuArrayRecursive(value(elementIndex).(names{fieldIndex}));
        end
    end
end
end

function assertDoubleScalar(value, fieldName)
if ~isa(value, 'double') || ~isscalar(value)
    contractFailure(sprintf('EXPECTED_CPU_DOUBLE_SCALAR_%s', fieldName));
end
end

function assertDoubleArray(value, fieldName)
if ~isa(value, 'double') || (~isempty(value) && ~isvector(value))
    contractFailure(sprintf('EXPECTED_CPU_DOUBLE_ARRAY_%s', fieldName));
end
end

function contractFailure(reason)
error('FullTaskGpuCandidate:INVALID_FROZEN_FIT_CONTRACT', ...
    'INVALID_FROZEN_FIT_CONTRACT: %s', reason);
end
