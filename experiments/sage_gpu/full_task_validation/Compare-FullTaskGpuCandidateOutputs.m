% Thin script entry retained at the implementation-plan path. MATLAB function
% names cannot contain hyphens, so the callable implementation uses the valid
% identifier compareFullTaskGpuCandidateOutputs in the adjacent .m file.
% The caller supplies these variables in its workspace:
% formalOutputDir, candidateOutputDir, taskSceneId, taskPrn, taskChannel,
% and optionally comparisonEvidenceDirectory.

try
    requiredInputs = {'formalOutputDir', 'candidateOutputDir', ...
        'taskSceneId', 'taskPrn', 'taskChannel'};
    for inputIndex = 1:numel(requiredInputs)
        if ~exist(requiredInputs{inputIndex}, 'var')
            error('FullTaskGpuCandidate:COMPARISON_FAILED', ...
                'COMPARISON_FAILED CALLER_INPUT_MISSING_%s', ...
                upper(requiredInputs{inputIndex}));
        end
    end
    evidenceDirectory = '';
    if exist('comparisonEvidenceDirectory', 'var')
        evidenceDirectory = char(comparisonEvidenceDirectory);
    end
    candidateComparison = compareFullTaskGpuCandidateOutputs( ...
        char(formalOutputDir), char(candidateOutputDir), ...
        char(taskSceneId), double(taskPrn), double(taskChannel), ...
        evidenceDirectory);
catch comparisonError
    if strcmp(comparisonError.identifier, ...
            'FullTaskGpuCandidate:COMPARISON_FAILED')
        rethrow(comparisonError);
    end
    error('FullTaskGpuCandidate:COMPARISON_FAILED', ...
        'COMPARISON_FAILED %s', ...
        getReport(comparisonError, 'extended', 'hyperlinks', 'off'));
end
