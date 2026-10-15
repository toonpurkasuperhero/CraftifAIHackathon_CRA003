// Custom detection (bbox) parser (generated).
// Scaffold validates the output layer and exposes the raw tensor(s); the DECODE
// block (per-model) populates `objectList` with NvDsInferObjectDetectionInfo.
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

#include "nvdsinfer_custom_impl.h"

extern "C" bool ParseConfigDetPgie(
    std::vector<NvDsInferLayerInfo> const& outputLayersInfo,
    NvDsInferNetworkInfo const& networkInfo,
    NvDsInferParseDetectionParams const& detectionParams,
    std::vector<NvDsInferObjectDetectionInfo>& objectList);

CHECK_CUSTOM_PARSE_FUNC_PROTOTYPE(ParseConfigDetPgie);

extern "C" bool ParseConfigDetPgie(
    std::vector<NvDsInferLayerInfo> const& outputLayersInfo,
    NvDsInferNetworkInfo const& networkInfo,
    NvDsInferParseDetectionParams const& detectionParams,
    std::vector<NvDsInferObjectDetectionInfo>& objectList)
{
    if (outputLayersInfo.empty()) return false;
    auto const& layer0 = outputLayersInfo[0];

    const unsigned numClasses = detectionParams.numClassesConfigured;
    const float netW = static_cast<float>(networkInfo.width);
    const float netH = static_cast<float>(networkInfo.height);
    const float* data = static_cast<const float*>(layer0.buffer);

    static bool logged = false;
    if (!logged) {
        logged = true;
        fprintf(stderr, "[ParseConfigDetPgie] first call: layer=%s numDims=%d "
                "networkInput=%.0fx%.0f numClasses=%u outputs=%zu\n",
                layer0.layerName ? layer0.layerName : "?",
                layer0.inferDims.numDims, netW, netH, numClasses,
                outputLayersInfo.size());
    }

    // ==== BEGIN GENERATED DECODE ====
    // YOLOv8 output shape after batch strip: [9, 8400]
    // d[0] = featureDim (4 + numClasses = 9), d[1] = numProposals (8400)
    // Each column j: data[row * numProposals + j]
    //   row 0 = cx, row 1 = cy, row 2 = w, row 3 = h,
    //   rows 4..8 = class scores (post-sigmoid probabilities).

    const unsigned numDims = layer0.inferDims.numDims;
    if (numDims < 2) return false;

    const unsigned dim0 = layer0.inferDims.d[0];
    const unsigned dim1 = layer0.inferDims.d[1];

    // Identify which dimension is the feature dim (4+numClasses) and which is
    // the proposal count. This lets the parser work regardless of whether the
    // engine emits [9,8400] or [8400,9].
    unsigned featureDim = 0;
    unsigned numProposals = 0;
    bool transposed = false; // true when layout is [numProposals, featureDim]

    if (dim0 == (4u + numClasses)) {
        featureDim = dim0;
        numProposals = dim1;
        transposed = false;
    } else if (dim1 == (4u + numClasses)) {
        featureDim = dim1;
        numProposals = dim0;
        transposed = true;
    } else {
        fprintf(stderr, "[ParseConfigDetPgie] ERROR: cannot identify feature dim "
                "(expected %u). Got dims %u x %u\n", 4u + numClasses, dim0, dim1);
        return false;
    }

    for (unsigned j = 0; j < numProposals; ++j) {
        // Find best class
        float maxScore = -1.0f;
        unsigned bestClass = 0;
        for (unsigned c = 0; c < numClasses; ++c) {
            float score;
            if (!transposed) {
                score = data[(4u + c) * numProposals + j];
            } else {
                score = data[j * featureDim + 4u + c];
            }
            if (score > maxScore) {
                maxScore = score;
                bestClass = c;
            }
        }

        // Threshold
        float thr = (bestClass < detectionParams.perClassPreclusterThreshold.size())
                     ? detectionParams.perClassPreclusterThreshold[bestClass]
                     : 0.35f;
        if (!std::isfinite(maxScore) || maxScore < thr) continue;

        // Read box coords
        float cx, cy, bw, bh;
        if (!transposed) {
            cx = data[0u * numProposals + j];
            cy = data[1u * numProposals + j];
            bw = data[2u * numProposals + j];
            bh = data[3u * numProposals + j];
        } else {
            cx = data[j * featureDim + 0u];
            cy = data[j * featureDim + 1u];
            bw = data[j * featureDim + 2u];
            bh = data[j * featureDim + 3u];
        }

        if (!std::isfinite(cx) || !std::isfinite(cy) ||
            !std::isfinite(bw) || !std::isfinite(bh) ||
            bw <= 0.0f || bh <= 0.0f) continue;

        // Convert from cx,cy,w,h (network pixel coords) to left,top,width,height
        float left   = cx - bw * 0.5f;
        float top    = cy - bh * 0.5f;

        // Clamp to network input area
        left   = std::max<float>(0.0f, std::min<float>(left, netW));
        top    = std::max<float>(0.0f, std::min<float>(top, netH));
        float right  = std::max<float>(0.0f, std::min<float>(cx + bw * 0.5f, netW));
        float bottom = std::max<float>(0.0f, std::min<float>(cy + bh * 0.5f, netH));

        float w = right - left;
        float h = bottom - top;
        if (w <= 1.0f || h <= 1.0f) continue;

        NvDsInferObjectDetectionInfo obj;
        obj.classId = bestClass;
        obj.left = left;
        obj.top = top;
        obj.width = w;
        obj.height = h;
        obj.detectionConfidence = maxScore;
        objectList.push_back(obj);
    }
    // ==== END GENERATED DECODE ====
    return true;
}