#include <cstdint>
#include <cstdio>
#include <cstring>
#include <vector>
#include <cmath>
#include <algorithm>

#include <opencv2/core.hpp>
#include <opencv2/imgproc.hpp>
#include <opencv2/dnn.hpp>

#include "nvcustomprocess.h"

#include <gst/gst.h>
#include "nvdsmeta.h"
#include "gstnvdsinfer.h"
#include "realsense_meta.h"
#include "render_meta.h"

static void write_nv12(const cv::Mat &bgr, NvDsCustomPostProcessFrameInCpu *in) {
    const int W = in->W, H = in->H;
    cv::Mat i420; cv::cvtColor(bgr, i420, cv::COLOR_BGR2YUV_I420);
    const uint8_t *ysrc = i420.data;
    const uint8_t *usrc = ysrc + (size_t)W * H;
    const uint8_t *vsrc = usrc + (size_t)(W / 2) * (H / 2);
    for (int r = 0; r < H; ++r)
        memcpy(in->Y_host + (size_t)r * in->Y_pitch, ysrc + (size_t)r * W, (size_t)W);
    const int cW = W / 2, cH = H / 2;
    for (int r = 0; r < cH; ++r) {
        uint8_t *dst = in->UV_host + (size_t)r * in->UV_pitch;
        const uint8_t *u = usrc + (size_t)r * cW, *v = vsrc + (size_t)r * cW;
        for (int c = 0; c < cW; ++c) { dst[2*c] = u[c]; dst[2*c+1] = v[c]; }
    }
}

static cv::Mat read_nv12_bgr(NvDsCustomPostProcessFrameInCpu *in) {
    const int W = in->W, H = in->H;
    cv::Mat yuv(H + H / 2, W, CV_8UC1);
    for (int r = 0; r < H; ++r)
        memcpy(yuv.ptr(r), in->Y_host + (size_t)r * in->Y_pitch, (size_t)W);
    for (int r = 0; r < H / 2; ++r)
        memcpy(yuv.ptr(H + r), in->UV_host + (size_t)r * in->UV_pitch, (size_t)W);
    cv::Mat bgr; cv::cvtColor(yuv, bgr, cv::COLOR_YUV2BGR_NV12); return bgr;
}

static const RsMeta *find_rs_meta(NvDsFrameMeta *fm) {
    if (!fm) return nullptr;
    static gsize t = 0;
    if (g_once_init_enter(&t)) {
        gsize v = (gsize) nvds_get_user_meta_type((gchar *) RS_NVDS_META_NAME);
        g_once_init_leave(&t, v);
    }
    for (NvDsMetaList *l = fm->frame_user_meta_list; l; l = l->next) {
        NvDsUserMeta *um = (NvDsUserMeta *) l->data;
        if (um && um->base_meta.meta_type == (NvDsMetaType) t)
            return (const RsMeta *) um->user_meta_data;
    }
    return nullptr;
}

struct TensorRef { const float *data; int d[4]; int ndim; long total; const char *name; };

static std::vector<TensorRef> collect_tensors(NvDsCustomPostProcessFrameInCpu *in) {
    std::vector<TensorRef> out;
    for (int mi = 0; mi < (int) in->num_tensor_metas; ++mi) {
        NvDsInferTensorMeta *tm = (NvDsInferTensorMeta *) in->tensor_metas[mi];
        if (!tm) continue;
        for (unsigned li = 0; li < tm->num_output_layers; ++li) {
            const float *host = (const float *) tm->out_buf_ptrs_host[li];
            if (!host) continue;
            NvDsInferLayerInfo &info = tm->output_layers_info[li];
            TensorRef t; t.data = host; t.name = info.layerName;
            int nd = (int) info.inferDims.numDims, base = 0;
            if (nd > 0 && info.inferDims.d[0] == 1) { base = 1; nd--; }
            t.ndim = nd > 4 ? 4 : nd; t.total = 1;
            for (int i = 0; i < 4; ++i) t.d[i] = 1;
            for (int i = 0; i < t.ndim; ++i) { t.d[i] = info.inferDims.d[base + i]; t.total *= t.d[i]; }
            out.push_back(t);
        }
    }
    return out;
}

static const TensorRef *find_tensor(const std::vector<TensorRef> &ts,
                                    int a, int b = -1, int c = -1, int d = -1) {
    int want = (b < 0) ? 1 : (c < 0) ? 2 : (d < 0) ? 3 : 4;
    for (const TensorRef &t : ts) {
        if (t.ndim != want || t.d[0] != a) continue;
        if (b >= 0 && t.d[1] != b) continue;
        if (c >= 0 && t.d[2] != c) continue;
        if (d >= 0 && t.d[3] != d) continue;
        return &t;
    }
    return nullptr;
}

static std::vector<int> nms_classaware(const std::vector<cv::Rect> &boxes,
        const std::vector<float> &scores, const std::vector<int> &classIds,
        float scoreThr, float iouThr) {
    std::vector<cv::Rect> off(boxes.size());
    const float STRIDE = 100000.0f;
    for (size_t i = 0; i < boxes.size(); ++i) {
        int s = (int)(classIds[i] * STRIDE);
        off[i] = cv::Rect(boxes[i].x + s, boxes[i].y + s, boxes[i].width, boxes[i].height);
    }
    std::vector<int> keep;
    cv::dnn::NMSBoxes(off, scores, scoreThr, iouThr, keep);
    return keep;
}

static void place_panel(cv::Mat &canvas, const cv::Mat &panel,
                        int r, int c, int rows, int cols) {
    int cw = canvas.cols / cols, ch = canvas.rows / rows;
    if (cw <= 0 || ch <= 0 || panel.empty()) return;
    cv::Mat dst = canvas(cv::Rect(c * cw, r * ch, cw, ch));
    cv::Mat resized; cv::resize(panel, resized, dst.size());
    resized.copyTo(dst);
}

static cv::Mat colormap_minmax(const float *data, int h, int w, int cvColormap) {
    cv::Mat f(h, w, CV_32FC1, (void *) data);
    double mn = 0, mx = 0; cv::minMaxLoc(f, &mn, &mx);
    double scale = (mx > mn) ? 255.0 / (mx - mn) : 0.0;
    cv::Mat u8; f.convertTo(u8, CV_8UC1, scale, -mn * scale);
    cv::Mat color; cv::applyColorMap(u8, color, cvColormap);
    return color;
}

extern "C" bool NvDsCustomPostProcess(NvDsCustomPostProcessFrameInCpu *in) {
    if (!in || !in->Y_host || !in->UV_host) return false;
    const int W = in->W, H = in->H;
    if (W < 2 || H < 2 || (W & 1) || (H & 1)) {
        fprintf(stderr, "[clahe_preprocess] surface must be even-sized, got %dx%d\n", W, H);
        return false;
    }

    NvDsInferTensorMeta *tm = in->num_tensor_metas
        ? (NvDsInferTensorMeta *) in->tensor_metas[0] : nullptr;
    const RsMeta *rs = find_rs_meta((NvDsFrameMeta *) in->frame_meta);
    (void) tm; (void) rs;

    // ==== BEGIN GENERATED PROCESS ====
    // CLAHE luma conditioning on NV12 Y plane.
    // Ramp parameters from PIR: measure=p50, off=0.30, full=0.15
    // CLAHE: clipLimit=2.0, tileGridSize=(8,8)

    constexpr int STEP = 4;
    constexpr float RAMP_OFF  = 0.30f;
    constexpr float RAMP_FULL = 0.15f;
    constexpr float CLIP_LIMIT = 2.0f;

    // --- Measure median luma (p50) on incoming Y plane, subsampled 4x ---
    // Build a contiguous Y mat respecting pitch
    cv::Mat Y(H, W, CV_8UC1);
    for (int r = 0; r < H; ++r)
        memcpy(Y.ptr(r), in->Y_host + (size_t)r * in->Y_pitch, (size_t)W);

    // Subsample every STEP-th pixel
    int sH = (H + STEP - 1) / STEP;
    int sW = (W + STEP - 1) / STEP;
    cv::Mat sampled(sH, sW, CV_32FC1);
    for (int r = 0; r < sH; ++r) {
        int sr = r * STEP;
        if (sr >= H) sr = H - 1;
        const uint8_t *row = Y.ptr<uint8_t>(sr);
        float *dst = sampled.ptr<float>(r);
        for (int c = 0; c < sW; ++c) {
            int sc = c * STEP;
            if (sc >= W) sc = W - 1;
            dst[c] = (static_cast<float>(row[sc]) - 16.0f) / 219.0f;
        }
    }

    // Compute median via sorting a flat copy
    std::vector<float> vals((size_t)sH * (size_t)sW);
    memcpy(vals.data(), sampled.data, vals.size() * sizeof(float));
    std::sort(vals.begin(), vals.end());
    float p50;
    {
        size_t n = vals.size();
        if (n == 0) {
            p50 = 0.5f;
        } else if (n % 2 == 1) {
            p50 = vals[n / 2];
        } else {
            p50 = 0.5f * (vals[n / 2 - 1] + vals[n / 2]);
        }
    }

    // Compute strength: s = clamp((off - p50) / (off - full), 0, 1)
    float s;
    {
        float denom = RAMP_OFF - RAMP_FULL; // 0.30 - 0.15 = 0.15
        if (std::fabs(denom) < 1e-9f) {
            s = (p50 <= RAMP_FULL) ? 1.0f : 0.0f;
        } else {
            s = (RAMP_OFF - p50) / denom;
            s = std::min<float>(std::max<float>(s, 0.0f), 1.0f);
        }
    }

    // If strength is 0, skip CLAHE entirely — daylight frame passes through.
    if (s > 0.0f) {
        // Apply CLAHE on Y plane
        cv::Ptr<cv::CLAHE> clahe = cv::createCLAHE(
            static_cast<double>(CLIP_LIMIT), cv::Size(8, 8));
        cv::Mat fixed;
        clahe->apply(Y, fixed);

        // Blend: out = Y*(1-s) + fixed*s
        cv::Mat blended;
        if (s >= 1.0f) {
            blended = fixed;
        } else {
            cv::addWeighted(Y, static_cast<double>(1.0f - s),
                            fixed, static_cast<double>(s), 0.0, blended);
        }

        // Write blended Y back to the NV12 surface, respecting pitch
        for (int r = 0; r < H; ++r)
            memcpy(in->Y_host + (size_t)r * in->Y_pitch,
                   blended.ptr(r), (size_t)W);
    }
    // UV plane is untouched — no chroma modification.

    // No model output to decode, no shapes to publish for this pre-NN node.
    // Emit an empty Builder so publish is always called.
    render_meta::Builder sb(W, H);
    sb.publish(in->frame_meta);
    // ==== END GENERATED PROCESS ====
    return true;
}

CHECK_NVCUSTOMPROCESS_CPU_PROTOTYPE(NvDsCustomPostProcess);