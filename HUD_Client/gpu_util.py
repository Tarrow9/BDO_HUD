import pyopencl as cl
import numpy as np

class GPUUtils:
    def __init__(self):
        platforms = cl.get_platforms()
        gpu_devices = [d for p in platforms for d in p.get_devices(device_type=cl.device_type.GPU)]
        if not gpu_devices:
            raise RuntimeError("No Available OpenCL GPU Devices!")

        self.ctx = cl.Context(devices=[gpu_devices[0]])
        self.queue = cl.CommandQueue(self.ctx)

        self.kernel_code = r"""
        __kernel void canny_edge(__global const uchar *img,
                                 __global uchar *output,
                                 int width, int height)
        {
            int x = get_global_id(0);
            int y = get_global_id(1);

            if (x > 1 && y > 1 && x < width - 1 && y < height - 1) {
                int left  = (y * width + (x - 1)) * 4;
                int right = (y * width + (x + 1)) * 4;
                int up    = ((y - 1) * width + x) * 4;
                int down  = ((y + 1) * width + x) * 4;

                int gx = (int)img[left] - (int)img[right];
                int gy = (int)img[up]   - (int)img[down];

                float mag = sqrt((float)(gx * gx + gy * gy));
                output[y * width + x] = (mag >= 180.0f && mag <= 275.0f) ? 255 : 0;
            }
        }
        """
        self.prg = cl.Program(self.ctx, self.kernel_code).build()

        # ✅ 커널 객체를 한 번만 생성해서 재사용
        self.kernel_canny = cl.Kernel(self.prg, "canny_edge")

        # 버퍼 재사용용
        self._w = self._h = None
        self._img_buf = None
        self._out_buf = None
        self._out_host = None

    def _ensure_buffers(self, w, h):
        if self._w == w and self._h == h and self._img_buf is not None:
            return
        self._w, self._h = w, h
        mf = cl.mem_flags
        self._img_buf = cl.Buffer(self.ctx, mf.READ_ONLY, size=w * h * 4)
        self._out_host = np.empty((h, w), dtype=np.uint8)
        self._out_buf = cl.Buffer(self.ctx, mf.WRITE_ONLY, size=self._out_host.nbytes)

    def gpu_canny(self, image_bgra: np.ndarray) -> np.ndarray:
        h, w = image_bgra.shape[:2]
        self._ensure_buffers(w, h)

        # host -> device
        cl.enqueue_copy(self.queue, self._img_buf, image_bgra, is_blocking=False)

        # ✅ 커널 재사용 호출
        self.kernel_canny.set_args(self._img_buf, self._out_buf, np.int32(w), np.int32(h))
        cl.enqueue_nd_range_kernel(self.queue, self.kernel_canny, (w, h), None)

        # device -> host
        cl.enqueue_copy(self.queue, self._out_host, self._out_buf, is_blocking=True)
        return self._out_host