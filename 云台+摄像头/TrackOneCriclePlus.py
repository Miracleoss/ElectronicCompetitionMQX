import sensor, image, time
from pyb import UART
import ustruct

# 初始化串口三、波特率115200 TXD:P4\PB10 RXD:P5\PB11
uart = UART(3, 115200, bits=8, parity=None, stop=1, timeout_char=1000)

# 初始化传感器
sensor.reset()

# 设置图像格式为RGB565，RGB格式相较于灰度图像速度更快
sensor.set_pixformat(sensor.RGB565)

# 设置图像分辨率为QQVGA（160x120），适用于快速处理
sensor.set_framesize(sensor.QQVGA)

# sensor.set_vflip(True)  # 设置垂直翻转，如果摄像头安装方向需要垂直翻转，启用此选项
sensor.set_hmirror(True)  # 设置水平翻转，如果摄像头安装方向需要水平翻转，启用此选项

# 跳过若干帧以便摄像头初始化并稳定，避免刚开始拍摄时的异常数据
sensor.skip_frames(time=2000)

# 创建时钟对象以便计算帧率
clock = time.clock()

# 定义过滤异常圆的阈值
FILTER_THRESHOLD = 20

# 初始化上一次检测到的圆的信息
last_x = None
last_y = None
last_r = None


def send_circle_data(x, y, r):
    global uart
    data = ustruct.pack("<BBBBBBBB",
                        0xA5,
                        0xA6,
                        int(x),
                        int(y),
                        int(r),
                        0,
                        0,
                        0x5B
                        )
    uart.write(data)
    print(data)


def send_no_circle_data():
    global uart
    data = ustruct.pack("<BBBBBBBB",
                        0xA5,
                        0xA6,
                        0,
                        0,
                        0,
                        0,
                        0,
                        0x5B
                        )
    uart.write(data)
    print(data)

while True:

    circle_detected = False  # 用于标记是否检测到圆形的标志
    # 每次循环都调用 tick() 更新时钟，计算帧率
    clock.tick()

    # 获取当前图像，并进行镜头畸变校正（参数1.8为校正系数，适用于大部分情况）
    img = sensor.snapshot().lens_corr(1.8)

    best_circle = None
    # 调整阈值和半径范围参数，以提高检测效果和性能
    for c in img.find_circles(
            threshold=3000,  # 设置霍夫变换的阈值。值越大，只有强度更高的圆会被检测到。
            x_margin=15,  # x方向的合并误差范围，增大会使相近的圆合并。
            y_margin=15,  # y方向的合并误差范围，增大会使相近的圆合并。
            r_margin=20,  # 半径方向的合并误差范围，增大会使半径相近的圆合并。
            r_min=2,  # 设置检测的最小圆半径
            r_max=30,  # 设置检测的最大圆半径
            r_step=2  # 设置检测半径时的步长
    ):
        if best_circle is None or c.magnitude() > best_circle.magnitude():
            best_circle = c

    if best_circle is not None:
        if last_x is not None and last_y is not None and last_r is not None:
            dx = abs(best_circle.x() - last_x)
            dy = abs(best_circle.y() - last_y)
            dr = abs(best_circle.r() - last_r)
            # 判断是否超过过滤阈值，如果超过则过滤掉该圆
            if dx > FILTER_THRESHOLD or dy > FILTER_THRESHOLD or dr > FILTER_THRESHOLD:
                print("Filtered out an abnormal circle.")
            else:
                # 绘制圆形，(255, 0, 0)表示圆的颜色为红色
                img.draw_circle(best_circle.x(), best_circle.y(), best_circle.r(), color=(255, 0, 0))

                # 打印圆的信息，包括圆心坐标和半径
                print("Circle found: x = {}, y = {}, radius = {}, magnitude = {}".format(best_circle.x(), best_circle.y(), best_circle.r(), best_circle.magnitude()))

                # 发送圆的信息
                send_circle_data(best_circle.x(), best_circle.y(), best_circle.r())
                last_x = best_circle.x()
                last_y = best_circle.y()
                last_r = best_circle.r()
                circle_detected = True  # 检测到圆形，设置标志为True
        else:
            # 第一次检测到圆，直接发送信息
            send_circle_data(best_circle.x(), best_circle.y(), best_circle.r())
            last_x = best_circle.x()
            last_y = best_circle.y()
            last_r = best_circle.r()
            circle_detected = True  # 检测到圆形，设置标志为True

    if not circle_detected:
        send_no_circle_data()  # 没有检测到圆形，发送相应信息
        last_x = None
        last_y = None
        last_r = None

    # 输出当前帧率，帮助调试和评估图像处理的性能
    print("FPS: %f" % clock.fps())
