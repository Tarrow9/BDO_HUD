import pyopencl as cl
import numpy as np

class GPUUtils:
    ctx = None
    queue = None
    prg = None

    def __init__(self):
        platforms = cl.get_platforms()  # 사용 가능한 OpenCL 플랫폼 가져오기
        gpu_devices = [d for p in platforms for d in p.get_devices(device_type=cl.device_type.GPU)]
        if not gpu_devices:
            raise RuntimeError("No Available OpenCL GPU Devices!")
        
        # GPU 디바이스 선택 (첫 번째 GPU 사용)
        self.ctx = cl.Context(devices=[gpu_devices[0]])
        self.queue = cl.CommandQueue(self.ctx)

        # OpenCL 커널 (Canny 엣지 검출)
        self.kernel_code = """
        __kernel void canny_edge(__global uchar *img, __global uchar *output, int width, int height) {
            int x = get_global_id(0);
            int y = get_global_id(1);
            if (x > 1 && y > 1 && x < width - 1 && y < height - 1) {
                int index = (y * width + x) * 4;  // RGBA 포맷에서 R값 위치
                uchar r = img[index];
                uchar g = img[index + 1];
                uchar b = img[index + 2];
                uchar gray = (uchar)(0.299f * r + 0.587f * g + 0.114f * b);
                int gx = img[(y * width + (x - 1)) * 4] - img[(y * width + (x + 1)) * 4];
                int gy = img[((y - 1) * width + x) * 4] - img[((y + 1) * width + x) * 4];
                float magnitude = sqrt((float)(gx * gx + gy * gy));
                output[y * width + x] = (magnitude >= 180 && magnitude <= 275) ? 255 : 0;
            }
        }
        """
        self.prg = self._get_gpu_canny_kernel()
    
    def _get_gpu_canny_kernel(self):
        if self.ctx is None:
            raise RuntimeError("OpenCL Context is not initialized!")
        return cl.Program(self.ctx, self.kernel_code).build()
    
    def gpu_canny(self, image):
        """OpenCL을 활용한 Canny Edge Detection"""
        if len(image.shape) == 3:
            height, width, _ = image.shape
        else:
            height, width = image.shape
        mf = cl.mem_flags
        img_buf = cl.Buffer(self.ctx, mf.READ_ONLY | mf.COPY_HOST_PTR, hostbuf=image)
        output = np.zeros((height, width), dtype=np.uint8)
        output_buf = cl.Buffer(self.ctx, mf.WRITE_ONLY, output.nbytes)
        self.prg.canny_edge(self.queue, (width, height), None, img_buf, output_buf, np.int32(width), np.int32(height))
        cl.enqueue_copy(self.queue, output, output_buf).wait()
        return output