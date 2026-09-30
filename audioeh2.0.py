import tkinter as tk
from tkinter import ttk, filedialog, messagebox, Scale, HORIZONTAL
import threading
import numpy as np
import sounddevice as sd
import soundfile as sf
import pedalboard
from pathlib import Path
import time
import os
import serial
import threading


def get_emotion():
        try:
            with open('emotion.txt', 'r') as f:
                return f.read().strip()
        except Exception as e:
            print(f"读取情绪文件时出错: {e}")
            return "读取错误"
        
class AudioProcessor:
    def __init__(self):
        # 先显示"加载中"界面，再异步初始化资源
        self.splash = tk.Tk()
        self.splash.title("初始化")
        self.splash.geometry("300x150")
        ttk.Label(self.splash, text="正在初始化，请稍候...").pack(pady=30)
        self.splash.update()  # 强制显示加载界面
        self.is_dragging_progress = False

        
        # 效果参数历史记录
        self.effect_history = {
            'reverb_room_size': [(0.0, 0.0)],       # (时间点, 混响强度)
            'distortion_level': [(0.0, 0.0)],   # (时间点, 失真度)
            'delay_time': [(0.0, 0.0)],   # (时间点, 延迟时间)
            'delay_feedback': [(0.0, 0.0)], # (时间点, 延迟反馈)
            'master_mix': [(0.0, 0.5)],    # (时间点, 主输出MIX)
            'bitcrush_bits': [(0.0, 8.0)],      # (时间点, Bitcrush位深度)
            'compressor_threshold': [(0.0, 0.0)],    # (时间点, 压缩器阈值)
            'compressor_ratio': [(0.0, 1.0)],
            'chorus_rate': [(0.0, 0.0)],    # (时间点,和声速率)
            'chorus_depth': [(0.0, 0.0)],                
            'phaser_feedback': [(0.0, 0.0)], 
            'phaser_rate': [(0.0, 0.0)]         # (时间点, 移相器速率)
        }

        # 录音相关变量
        self.is_recording = False
        self.recorded_data = []
        # 在子线程中初始化资源，避免阻塞GUI
        self.init_thread = threading.Thread(target=self.async_init, daemon=True)
        self.init_thread.start()
        self.check_init_done()  # 检查初始化是否完成



    def async_init(self):
        """异步初始化音频资源（避免阻塞主线程）"""
        try:
            # 音频参数
            self.sample_rate = 44100
            self.block_size = 1024  # 减小块大小以提高响应速度
            self.channels = 2

            # 效果参数（默认值）
            self.reverb_room_size = 0.0  # 混响房间大小
            self.distortion_level = 0.0  # 失真度 (0.0-1.0)
            self.delay_time = 0.0       # 延迟时间 (秒)
            self.delay_feedback = 0.0   # 延迟反馈 (0.0-1.0)
            self.master_mix = 0.2       # 主输出MIX (0.0=仅原始, 1.0=仅效果)
            self.bitcrush_bits = 8.0    # Bitcrush位深度
            self.compressor_threshold = 0.0  # 压缩器阈值
            self.compressor_ratio = 1.0
            self.chorus_rate = 0.0      #和声速率
            self.chorus_depth = 0.0
            self.phaser_rate = 0.0      # 移相器速率
            self.phaser_feedback = 0.0

            # 初始化效果链
            self.init_effect_chains()

            # 检查音频设备
            sd.query_devices()  # 触发设备检测

            # 音频文件和流状态
            self.audio_folder = ""
            self.audio_files = []
            self.current_file_index = 0
            self.audio_data = None
            self.sample_rate = None
            self.file_position = 0
            self.is_playing = False
            self.is_recording = False
            self.stream = None
            self.block_size = 1024
            self.channels = 2
            # switch变量
            self.switch = 0

            # 初始化完成标志
            self.init_success = True
        except Exception as e:
            self.init_error = str(e)
            self.init_success = False

    def init_effect_chains(self):
        """初始化效果链，创建效果路径和直通路径"""
        # 效果处理器
        self.reverb = pedalboard.Reverb(
            room_size=self.reverb_room_size,
            damping=0.5,
            wet_level=1.0,  # 内部混响使用全部湿信号，由主MIX控制干湿比例
            dry_level=0.0,
            width=1.0
        )

        self.distortion = pedalboard.Distortion(drive_db=self.distortion_level * 40)

        self.delay = pedalboard.Delay(
            delay_seconds=self.delay_time,
            feedback=self.delay_feedback,
            mix=0.5  # 延迟混合比例固定为0.5
        )

        self.bitcrush = pedalboard.Bitcrush(bit_depth=self.bitcrush_bits)
        self.compressor = pedalboard.Compressor(threshold_db=self.compressor_threshold, ratio=self.compressor_ratio)
        self.chorus = pedalboard.Chorus(rate_hz=self.chorus_rate, depth=self.chorus_depth)
        self.phaser = pedalboard.Phaser(rate_hz=self.phaser_rate, feedback=self.phaser_feedback)
        # 效果链 - 应用所有效果
        self.effect_chain = pedalboard.Pedalboard([
            self.distortion,
            self.delay,
            self.reverb,
            self.bitcrush,
            self.compressor,
            self.chorus,
            self.phaser,
        ])

        # 直通链 - 不应用任何效果
        self.dry_chain = pedalboard.Pedalboard([])

    def check_init_done(self):
        """检查初始化是否完成，完成后显示主界面"""
        if not self.init_thread.is_alive():
            self.splash.destroy()  # 关闭加载界面
            if self.init_success:
                self.create_main_gui()  # 显示主界面
            else:
                # 显示错误信息
                error_window = tk.Toplevel()
                error_window.title("初始化失败")
                error_window.geometry("400x200")
                ttk.Label(error_window, text=f"初始化失败：\n{self.init_error}").pack(pady=20)
                ttk.Button(error_window, text="退出", command=error_window.destroy).pack(pady=10)
                error_window.transient(self.root)  # 设置为主窗口的子窗口
                error_window.grab_set()  # 模态窗口
        else:
            # 继续等待
            self.splash.after(100, self.check_init_done)

    def create_main_gui(self):
        """创建主界面（初始化完成后调用）"""
        self.root = tk.Tk()
        self.root.title("音频效果处理器")
        self.root.geometry("800x900")  # 增加窗口高度以容纳新控件
        self.root.configure(bg="#f0f0f0")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)  # 绑定窗口关闭事件

        # 创建样式对象
        self.style = ttk.Style()
        self.style.configure("TLabel", background="#f0f0f0")
        self.style.configure("TFrame", background="#f0f0f0")

        # 状态栏
        self.status_var = tk.StringVar(value="就绪")
        self.status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

         # 文件夹选择部分
        folder_frame = ttk.Frame(self.root, padding=5)
        folder_frame.pack(fill=tk.X)
        
        ttk.Label(folder_frame, text="音频文件夹:").pack(side=tk.LEFT)
        self.folder_var = tk.StringVar(value="未选择文件夹")
        ttk.Label(folder_frame, textvariable=self.folder_var).pack(side=tk.LEFT, padx=5)
        ttk.Button(folder_frame, text="选择文件夹", command=self.select_folder).pack(side=tk.LEFT)
        
        # 文件列表部分
        files_frame = ttk.LabelFrame(self.root, text="音频文件列表", padding=10)
        files_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.file_listbox = tk.Listbox(files_frame, selectmode=tk.SINGLE, height=5)
        self.file_listbox.pack(fill=tk.BOTH, expand=True)

        # 进度条区域 - 改进为可拖动
        progress_frame = tk.Frame(self.root, bg="#f0f0f0", height=30)
        progress_frame.pack(fill=tk.X, padx=20, pady=5)

        self.progress_var = tk.DoubleVar(value=0.0)
        self.progress_bar = ttk.Progressbar(
            progress_frame,
            variable=self.progress_var,
            maximum=100.0,
            orient=HORIZONTAL,
            length=660
        )
        self.progress_bar.pack(fill=tk.X, padx=3)

        # 绑定进度条点击和拖动事件
        self.progress_bar.bind("<Button-1>", self.on_progress_click)
        self.progress_bar.bind("<B1-Motion>", self.on_progress_drag)
        self.progress_bar.bind("<ButtonRelease-1>", self.on_progress_release)

        self.time_label = tk.Label(
            progress_frame,
            text="00:00 / 00:00",
            font=("Arial", 9),
            bg="#d8d4d4"
        )
        self.time_label.place(relx=0.3, rely=0.3, anchor="center")

        # 效果控制区域
        effects_frame = tk.LabelFrame(self.root, text="效果控制", bg="#f0f0f0", padx=10, pady=10)
        effects_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # 主输出MIX控制
        master_mix_frame = tk.Frame(effects_frame, bg="#f0f0f0")
        master_mix_frame.pack(fill=tk.X, pady=5)

        tk.Label(master_mix_frame, text="效果混合:", bg="#f0f0f0").pack(side=tk.LEFT, padx=5)
        self.master_mix_value = tk.DoubleVar(value=self.master_mix)
        self.master_mix_scale = Scale(
            master_mix_frame,
            variable=self.master_mix_value,
            from_=0.0,
            to=1.0,
            resolution=0.01,
            orient=HORIZONTAL,
            length=400,
            bg="#f0f0f0",
            command=self.update_master_mix
        )
        self.master_mix_scale.pack(side=tk.LEFT, padx=5)

        self.master_mix_display = tk.Label(master_mix_frame, text=f"{self.master_mix:.2f}", width=8, bg="#f0f0f0")
        self.master_mix_display.pack(side=tk.LEFT, padx=5)

        # 混响控制
        reverb_room_size_frame = tk.Frame(effects_frame, bg="#f0f0f0")
        reverb_room_size_frame.pack(fill=tk.X, pady=5)

        tk.Label(reverb_room_size_frame, text="混响强度:", bg="#f0f0f0").pack(side=tk.LEFT, padx=5)
        self.reverb_room_size_value = tk.DoubleVar(value=self.reverb_room_size)
        self.reverb_room_size_scale = Scale(
            reverb_room_size_frame,
            variable=self.reverb_room_size_value,
            from_=0.0,
            to=1.0,
            resolution=0.01,
            orient=HORIZONTAL,
            length=400,
            bg="#f0f0f0",
            command=self.update_reverb
        )
        self.reverb_room_size_scale.pack(side=tk.LEFT, padx=5)

        self.reverb_room_size_display = tk.Label(reverb_room_size_frame, text=f"{self.reverb_room_size:.2f}", width=8, bg="#f0f0f0")
        self.reverb_room_size_display.pack(side=tk.LEFT, padx=5)

        # 失真控制
        distortion_level_frame = tk.Frame(effects_frame, bg="#f0f0f0")
        distortion_level_frame.pack(fill=tk.X, pady=5)

        tk.Label(distortion_level_frame, text="失真度:", bg="#f0f0f0").pack(side=tk.LEFT, padx=5)
        self.distortion_level_value = tk.DoubleVar(value=self.distortion_level)
        self.distortion_level_scale = Scale(
            distortion_level_frame,
            variable=self.distortion_level_value,
            from_=0.0,
            to=2.0,
            resolution=0.01,
            orient=HORIZONTAL,
            length=400,
            bg="#f0f0f0",
            command=self.update_distortion
        )
        self.distortion_level_scale.pack(side=tk.LEFT, padx=5)

        self.distortion_level_display = tk.Label(distortion_level_frame, text=f"{self.distortion_level:.2f}", width=8, bg="#f0f0f0")
        self.distortion_level_display.pack(side=tk.LEFT, padx=5)

        # 延迟时间控制
        delay_time_frame = tk.Frame(effects_frame, bg="#f0f0f0")
        delay_time_frame.pack(fill=tk.X, pady=5)

        tk.Label(delay_time_frame, text="延迟时间(秒):", bg="#f0f0f0").pack(side=tk.LEFT, padx=5)
        self.delay_time_value = tk.DoubleVar(value=self.delay_time)
        self.delay_time_scale = Scale(
            delay_time_frame,
            variable=self.delay_time_value,
            from_=0.0,
            to=1.0,
            resolution=0.01,
            orient=HORIZONTAL,
            length=400,
            bg="#f0f0f0",
            command=self.update_delay_time
        )
        self.delay_time_scale.pack(side=tk.LEFT, padx=5)

        self.delay_time_display = tk.Label(delay_time_frame, text=f"{self.delay_time:.2f}", width=8, bg="#f0f0f0")
        self.delay_time_display.pack(side=tk.LEFT, padx=5)

        # 延迟反馈控制
        delay_feedback_frame = tk.Frame(effects_frame, bg="#f0f0f0")
        delay_feedback_frame.pack(fill=tk.X, pady=5)

        tk.Label(delay_feedback_frame, text="延迟回授:", bg="#f0f0f0").pack(side=tk.LEFT, padx=5)
        self.delay_feedback_value = tk.DoubleVar(value=self.delay_feedback)
        self.delay_feedback_scale = Scale(
            delay_feedback_frame,
            variable=self.delay_feedback_value,
            from_=0.0,
            to=1.0,
            resolution=0.01,
            orient=HORIZONTAL,
            length=400,
            bg="#f0f0f0",
            command=self.update_delay_feedback
        )
        self.delay_feedback_scale.pack(side=tk.LEFT, padx=5)

        self.delay_feedback_display = tk.Label(delay_feedback_frame, text=f"{self.delay_feedback:.2f}", width=8, bg="#f0f0f0")
        self.delay_feedback_display.pack(side=tk.LEFT, padx=5)

        # Bitcrush控制
        bitcrush_bits_frame = tk.Frame(effects_frame, bg="#f0f0f0")
        bitcrush_bits_frame.pack(fill=tk.X, pady=5)

        tk.Label(bitcrush_bits_frame, text="Bitcrush位深度:", bg="#f0f0f0").pack(side=tk.LEFT, padx=5)
        self.bitcrush_bits_value = tk.DoubleVar(value=self.bitcrush_bits)
        self.bitcrush_bits_scale = Scale(
            bitcrush_bits_frame,
            variable=self.bitcrush_bits_value,
            from_=1.0,
            to=10.0,  # 扩展上限到10位
            resolution=0.1,  
            orient=HORIZONTAL,
            length=400,
            bg="#f0f0f0",
            command=self.update_bitcrush
        )
        self.bitcrush_bits_scale.pack(side=tk.LEFT, padx=5)

        self.bitcrush_bits_display = tk.Label(bitcrush_bits_frame, text=f"{self.bitcrush_bits:.1f}", width=8, bg="#f0f0f0")
        self.bitcrush_bits_display.pack(side=tk.LEFT, padx=5)
        # 压缩器阈值控制
        compressor_threshold_frame = tk.Frame(effects_frame, bg="#f0f0f0")
        compressor_threshold_frame.pack(fill=tk.X, pady=5)

        tk.Label(compressor_threshold_frame, text="压缩器阈值:", bg="#f0f0f0").pack(side=tk.LEFT, padx=5)
        self.compressor_threshold_value = tk.DoubleVar(value=self.compressor_threshold)
        self.compressor_threshold_scale = Scale(
            compressor_threshold_frame,
            variable=self.compressor_threshold_value,
            from_=-30.0,
            to=10.0,
            resolution=0.1,
            orient=HORIZONTAL,
            length=400,
            bg="#f0f0f0",
            command=self.update_compressor_threshold
        )
        self.compressor_threshold_scale.pack(side=tk.LEFT, padx=5)

        self.compressor_threshold_display = tk.Label(compressor_threshold_frame, text=f"{self.compressor_threshold:.1f}", width=8, bg="#f0f0f0")
        self.compressor_threshold_display.pack(side=tk.LEFT, padx=5)

        # 压缩器比率控制
        compressor_ratio_frame = tk.Frame(effects_frame, bg="#f0f0f0")
        compressor_ratio_frame.pack(fill=tk.X, pady=5)

        tk.Label(compressor_ratio_frame, text="压缩器比率:", bg="#f0f0f0").pack(side=tk.LEFT, padx=5)
        self.compressor_ratio_value = tk.DoubleVar(value=self.compressor_ratio)
        self.compressor_ratio_scale = Scale(
            compressor_ratio_frame,
            variable=self.compressor_ratio_value,
            from_=1.0,
            to=8.0,
            resolution=0.1,
            orient=HORIZONTAL,
            length=400,
            bg="#f0f0f0",
            command=self.update_compressor_ratio
        )
        self.compressor_ratio_scale.pack(side=tk.LEFT, padx=5)

        self.compressor_ratio_display = tk.Label(compressor_ratio_frame, text=f"{self.compressor_ratio:.1f}", width=8, bg="#f0f0f0")
        self.compressor_ratio_display.pack(side=tk.LEFT, padx=5)

        # 和声速率控制
        chorus_rate_frame = tk.Frame(effects_frame, bg="#f0f0f0")
        chorus_rate_frame.pack(fill=tk.X, pady=5)

        tk.Label(chorus_rate_frame, text="和声速率:", bg="#f0f0f0").pack(side=tk.LEFT, padx=5)
        self.chorus_rate_value = tk.DoubleVar(value=self.chorus_rate)
        self.chorus_rate_scale = Scale(
            chorus_rate_frame,
            variable=self.chorus_rate_value,
            from_=0.0,
            to=1.2,
            resolution=0.01,
            orient=HORIZONTAL,
            length=400,
            bg="#f0f0f0",
            command=self.update_chorus_rate
        )
        self.chorus_rate_scale.pack(side=tk.LEFT, padx=5)

        self.chorus_rate_display = tk.Label(chorus_rate_frame, text=f"{self.chorus_rate:.1f}", width=8, bg="#f0f0f0")
        self.chorus_rate_display.pack(side=tk.LEFT, padx=5)

        # 和声深度控制
        chorus_depth_frame = tk.Frame(effects_frame, bg="#f0f0f0")
        chorus_depth_frame.pack(fill=tk.X, pady=5)

        tk.Label(chorus_depth_frame, text="和声深度:", bg="#f0f0f0").pack(side=tk.LEFT, padx=5)
        self.chorus_depth_value = tk.DoubleVar(value=self.chorus_depth)
        self.chorus_depth_scale = Scale(
            chorus_depth_frame,
            variable=self.chorus_depth_value,
            from_=0.0,
            to=1.0,
            resolution=0.01,
            orient=HORIZONTAL,
            length=400,
            bg="#f0f0f0",
            command=self.update_chorus_depth
        )
        self.chorus_depth_scale.pack(side=tk.LEFT, padx=5)

        self.chorus_depth_display = tk.Label(chorus_depth_frame, text=f"{self.chorus_depth:.1f}", width=8, bg="#f0f0f0")
        self.chorus_depth_display.pack(side=tk.LEFT, padx=5)


        # 移相器速率控制
        phaser_rate_frame = tk.Frame(effects_frame, bg="#f0f0f0")
        phaser_rate_frame.pack(fill=tk.X, pady=5)

        tk.Label(phaser_rate_frame, text="移相器速率:", bg="#f0f0f0").pack(side=tk.LEFT, padx=5)
        self.phaser_rate_value = tk.DoubleVar(value=self.phaser_rate)
        self.phaser_rate_scale = Scale(
            phaser_rate_frame,
            variable=self.phaser_rate_value,
            from_=0.0,
            to=2.0,
            resolution=0.01,
            orient=HORIZONTAL,
            length=400,
            bg="#f0f0f0",
            command=self.update_phaser_rate
        )
        self.phaser_rate_scale.pack(side=tk.LEFT, padx=5)

        self.phaser_rate_display = tk.Label(phaser_rate_frame, text=f"{self.phaser_rate:.1f}", width=8, bg="#f0f0f0")
        self.phaser_rate_display.pack(side=tk.LEFT, padx=5)

        # 移相器回授控制
        phaser_feedback_frame = tk.Frame(effects_frame, bg="#f0f0f0")
        phaser_feedback_frame.pack(fill=tk.X, pady=5)

        tk.Label(phaser_feedback_frame, text="移相器回授:", bg="#f0f0f0").pack(side=tk.LEFT, padx=5)
        self.phaser_feedback_value = tk.DoubleVar(value=self.phaser_feedback)
        self.phaser_feedback_scale = Scale(
            phaser_feedback_frame,
            variable=self.phaser_feedback_value,
            from_=-1.0,
            to=1.0,
            resolution=0.01,
            orient=HORIZONTAL,
            length=400,
            bg="#f0f0f0",
            command=self.update_phaser_feedback
        )
        self.phaser_feedback_scale.pack(side=tk.LEFT, padx=5)

        self.phaser_feedback_display = tk.Label(phaser_feedback_frame, text=f"{self.phaser_rate:.1f}", width=8, bg="#f0f0f0")
        self.phaser_feedback_display.pack(side=tk.LEFT, padx=5)

        # 按钮区域
        button_frame = tk.Frame(self.root, bg="#f0f0f0")
        button_frame.pack(fill=tk.X, padx=20, pady=10)

        self.play_button = ttk.Button(button_frame, text="播放", command=self.start_playback)
        self.play_button.pack(side=tk.LEFT, padx=5)

        self.reset_button = ttk.Button(button_frame, text="重置效果", command=self.reset_effects)
        self.reset_button.pack(side=tk.LEFT, padx=5)

        self.record_button = ttk.Button(button_frame, text="结束", command=self.end_recording)
        self.record_button.pack(side=tk.LEFT, padx=5)
         # switch控制按钮
        self.switch_button = ttk.Button(button_frame, text="切换下一首 (Switch=1)", command=self.toggle_switch)
        self.switch_button.pack(side=tk.LEFT, padx=5)
        
        # 状态显示
        status_frame = ttk.Frame(self.root, padding=10)
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)
        
        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(status_frame, textvariable=self.status_var).pack(side=tk.LEFT)
        
        self.select_label = ttk.Label(status_frame, text="未加载音频")
        self.select_label.pack(side=tk.RIGHT)
        self.root.after(100, self.loop_adjust_effects)

        #Arduino通信
        self.ser = serial.Serial('COM5', 9600, timeout=1)  # 根据实际修改端口
        self.serial_thread = threading.Thread(target=self.listen_serial)
        self.serial_thread.daemon = True
        self.serial_thread.start()
        # 启动主循环
        self.root.mainloop()
        

    def select_folder(self):
        """选择音频文件夹并加载其中的音频文件"""
        folder_path = filedialog.askdirectory(title="选择音频文件夹")
        if folder_path:
            self.audio_folder = folder_path
            self.folder_var.set(f"已选择: {Path(folder_path).name}")
            self.load_audio_files()
            if self.audio_files:
                self.load_audio(self.audio_files[0])
                self.update_file_listbox()
    
    def load_audio_files(self):
        """加载文件夹中的所有音频文件"""
        self.audio_files = []
        valid_extensions = ['.wav', '.mp3', '.flac', '.aiff']
        
        for file in os.listdir(self.audio_folder):
            if any(file.lower().endswith(ext) for ext in valid_extensions):
                self.audio_files.append(os.path.join(self.audio_folder, file))
        
        self.audio_files.sort()  # 按文件名排序
    
    def update_file_listbox(self):
        """更新文件列表显示"""
        self.file_listbox.delete(0, tk.END)
        for i, file in enumerate(self.audio_files):
            filename = Path(file).name
            if i == self.current_file_index:
                self.file_listbox.insert(tk.END, f"▶ {filename}")
                self.file_listbox.itemconfig(self.current_file_index, fg="red")
            else:
                self.file_listbox.insert(tk.END, f"  {filename}")

    def load_audio(self, file_path):
        """加载音频文件"""
        try:
            # 停止当前播放（如果正在播放）
            if self.is_playing:
                self.stop_playback()

            self.audio_file = file_path
            self.audio_data, self.sample_rate = sf.read(file_path)
            self.file_position = 0  # 重置播放位置

             # 关闭并重置音频流
            if self.stream:
                try:
                    self.stream.stop()
                    self.stream.close()
                    self.stream = None
                except Exception as e:
                    print(f"关闭流时出错: {e}")

                # 清空录音数据
                self.recorded_data = []

                self.audio_file = file_path
                self.audio_data, self.sample_rate = sf.read(file_path)
                self.file_position = 0  # 重置播放位置

            # 确保音频是立体声（如果是单声道则转换）
            if len(self.audio_data.shape) == 1:
                self.audio_data = np.column_stack((self.audio_data, self.audio_data))

            # 更新当前文件索引
            self.current_file_index = self.audio_files.index(file_path)
            
            self.select_label.config(text=f"已加载: {Path(file_path).name}")
            self.status_var.set(f"已加载: {Path(file_path).name}")
            self.update_file_listbox()
            # 更新进度条最大值
            self.total_frames = len(self.audio_data)
            self.update_progress()

            # 重置效果历史
            self.reset_effect_history()
        except Exception as e:
            messagebox.showerror("错误", f"加载失败: {str(e)}")
            self.status_var.set("加载失败")
            self.audio_data = None  # 确保加载失败时音频数据为空   

    def start_playback(self):
        """开始播放音频"""
        if self.audio_data is None:
            messagebox.showinfo("提示", "请先加载音频文件")
            return
        if not self.is_playing:
            self.is_playing = True
            self.recorded_data = []
            self.status_var.set("播放中...")
        else: return    

        # 创建音频流
        try:
            self.stream = sd.OutputStream(
                samplerate=self.sample_rate,
                blocksize=self.block_size,
                channels=self.channels,
                callback=self.audio_callback
            )
            self.stream.start()
            if not self.is_recording:
                self.is_recording = True

        except Exception as e:
            messagebox.showerror("错误", f"播放失败: {str(e)}")
            self.is_playing = False
            self.play_button.config(text="播放")
            self.status_var.set("播放失败")

        # 开始更新进度条
        self.update_progress()

    def pause_playback(self):
        """暂停播放音频"""
        self.is_playing = False
        self.play_button.config(text="播放")
        self.status_var.set("已暂停")

        if self.stream:
            try:
                self.stream.stop()
            except Exception as e:
                print(f"停止流时出错: {e}")

    def stop_playback(self):
        """停止播放并重置位置"""
        self.is_playing = False
        self.file_position = 0
        self.play_button.config(text="播放")
        self.status_var.set("已停止")

        if self.stream:
            try:
                self.stream.stop()
                self.stream.close()
                self.stream = None
            except Exception as e:
                print(f"关闭流时出错: {e}")

        # 更新进度条
        self.update_progress()

    def toggle_switch(self):
        """切换switch状态并处理音频文件切换"""
        self.switch = 1
        self.status_var.set("Switch = 1，准备切换到下一首")
        
        # 模拟GUI事件循环后的处理
        self.root.after(100, self.process_switch)
    
    def process_switch(self):
        """处理switch=1的情况，切换到下一首音频"""
        if self.switch == 1 and self.audio_files:
            # 计算下一个文件索引
            next_index = (self.current_file_index + 1) % len(self.audio_files)
            
            # 加载下一个文件
            self.load_audio(self.audio_files[next_index])
            
            # 如果当前正在播放，则自动开始播放新文件
            if self.is_playing:
                self.start_playback()
            
            # 重置switch
            self.switch = 0
            self.status_var.set(f"已切换到: {Path(self.audio_files[next_index]).name}")
            
    def audio_callback(self, outdata, frames, time, status):
        """音频流回调函数 - 动态应用效果历史记录中的参数"""
        if status:
            print(f"状态: {status}")

        if self.file_position >= len(self.audio_data):
            self.root.after(0, self.stop_playback)
            raise sd.CallbackStop()

        available = len(self.audio_data) - self.file_position
        if frames > available:
            frames = available

        audio_chunk = self.audio_data[self.file_position:self.file_position + frames]

        # 计算当前块的开始和结束时间
        current_time = self.file_position / self.sample_rate
        end_time = (self.file_position + frames) / self.sample_rate

        # 检查是否有效果参数在当前块内发生变化
        effects_changed = False
        for effect_type in self.effect_history:
            history = self.effect_history[effect_type]
            # 查找在当前块内的参数变化
            for point in history:
                if current_time <= point[0] < end_time:
                    effects_changed = True
                    break
            if effects_changed:
                break

        # 如果有参数变化，分多段处理音频
        if effects_changed:
            # 找到所有在当前块内的变化点
            change_points = []
            for effect_type in self.effect_history:
                for point in self.effect_history[effect_type]:
                    if current_time <= point[0] < end_time:
                        change_points.append(point[0])

            # 排序变化点
            change_points = sorted(list(set(change_points)))
            # 添加当前块的开始和结束时间
            change_points = [current_time] + change_points + [end_time]

            processed = np.zeros_like(audio_chunk)
            segment_start_frame = 0

            for i in range(len(change_points) - 1):
                segment_start_time = change_points[i]
                segment_end_time = change_points[i+1]

                # 计算对应的帧范围
                segment_start_frame = int(segment_start_time * self.sample_rate - self.file_position)
                segment_end_frame = int(segment_end_time * self.sample_rate - self.file_position)
                segment_end_frame = min(segment_end_frame, frames)  # 确保不超出当前块

                # 获取该时间段的效果参数
                effect_params = {}
                for effect_type in self.effect_history:
                    start_value = self.get_effect_at_time(effect_type, segment_start_time)
                    end_value = self.get_effect_at_time(effect_type, segment_end_time)
                    effect_params[effect_type] = (start_value, end_value)

                # 处理该段音频，进行线性插值
                segment = audio_chunk[segment_start_frame:segment_end_frame]
                if len(segment) > 0:
                    segment_frames = len(segment)
                    for frame in range(segment_frames):
                        frame_time = segment_start_time + (frame / self.sample_rate)
                        lerp_factor = (frame_time - segment_start_time) / (segment_end_time - segment_start_time)
                        for effect_type in effect_params:
                            start_value, end_value = effect_params[effect_type]
                            value = start_value + (end_value - start_value) * lerp_factor
                            self.update_effect_parameter(effect_type, value)

                        try:
                            effect_signal = self.effect_chain(segment[frame:frame+1], self.sample_rate, reset=False)
                            dry_signal = self.dry_chain(segment[frame:frame+1], self.sample_rate, reset=False)
                            mixed = (effect_signal * self.master_mix) + (dry_signal * (1.0 - self.master_mix))
                            mixed = np.clip(mixed, -1.0, 1.0)
                            processed[segment_start_frame + frame:segment_start_frame + frame + 1] = mixed
                        except Exception as e:
                            print(f"处理音频段时出错: {e}")
                            processed[segment_start_frame + frame:segment_start_frame + frame + 1] = np.zeros_like(segment[frame:frame+1])
        else:
            # 如果没有参数变化，整块处理
            try:
                # 获取当前时间的效果参数
                for effect_type in self.effect_history:
                    value = self.get_effect_at_time(effect_type, current_time)
                    self.update_effect_parameter(effect_type, value)

                effect_signal = self.effect_chain(audio_chunk, self.sample_rate, reset=False)
                dry_signal = self.dry_chain(audio_chunk, self.sample_rate, reset=False)
                mixed = (effect_signal * self.master_mix) + (dry_signal * (1.0 - self.master_mix))
                mixed = np.clip(mixed, -1.0, 1.0)
                processed = mixed
            except Exception as e:
                print(f"应用效果时出错: {e}")
                processed = np.zeros_like(audio_chunk)

        outdata[:frames] = processed

        # 录音逻辑
        if self.is_recording:
            self.recorded_data.append(processed.copy())

        self.file_position += frames

    def update_progress(self):
        """更新进度条和时间显示"""
        if self.audio_data is not None and not self.is_dragging_progress:
            # 计算当前进度百分比
            if self.total_frames > 0:
                progress = (self.file_position / self.total_frames) * 100
                self.progress_var.set(progress)

                # 计算当前时间和总时间
                current_seconds = int(self.file_position / self.sample_rate)
                total_seconds = int(len(self.audio_data) / self.sample_rate)

                # 格式化时间显示
                current_time = time.strftime('%M:%S', time.gmtime(current_seconds))
                total_time = time.strftime('%M:%S', time.gmtime(total_seconds))

                self.time_label.config(text=f"{current_time} / {total_time}")

        # 如果正在播放，继续更新进度条
        if self.is_playing and not self.is_dragging_progress:
            self.root.after(200, self.update_progress)

    def on_progress_click(self, event):
        """处理进度条点击事件"""
        self.is_dragging_progress = True

        # 计算点击位置对应的进度
        progress_bar = event.widget
        x = event.x
        width = progress_bar.winfo_width()
        progress = (x / width) * 100

        # 更新进度条显示
        self.progress_var.set(progress)

        # 计算对应的音频位置
        if self.audio_data is not None and self.total_frames > 0:
            new_position = int((progress / 100) * self.total_frames)
            self.file_position = new_position

    def on_progress_drag(self, event):
        """处理进度条拖动事件"""
        if self.is_dragging_progress:
            progress_bar = event.widget
            x = event.x
            width = progress_bar.winfo_width()

            # 确保x在有效范围内
            x = max(0, min(x, width))

            progress = (x / width) * 100

            # 更新进度条显示
            self.progress_var.set(progress)

            # 计算对应的音频位置
            if self.audio_data is not None and self.total_frames > 0:
                new_position = int((progress / 100) * self.total_frames)
                self.file_position = new_position

    def on_progress_release(self, event):
        """处理进度条释放事件"""
        self.is_dragging_progress = False

        # 计算释放位置对应的进度
        progress_bar = event.widget
        x = event.x
        width = progress_bar.winfo_width()

        # 确保x在有效范围内
        x = max(0, min(x, width))

        progress = (x / width) * 100

        # 更新进度条显示
        self.progress_var.set(progress)
        self.update_progress()

        # 跳转到对应的音频位置
        if self.audio_data is not None and self.total_frames > 0:
            new_position = int((progress / 100) * self.total_frames)
            self.file_position = new_position

            # 如果正在播放，确保音频流继续
            if self.is_playing and self.stream:
                try:
                    self.stream.abort()  # 重置流状态
                    self.stream.start()  # 重新启动流
                except Exception as e:
                    print(f"重置流时出错: {e}")

            # 更新效果历史记录的基准时间
            self.reset_effect_history()

        

    def listen_serial(self):
        """监听串口并执行对应方法"""
        while True:
            if self.ser.in_waiting:
                monitor = self.ser.readline().decode('utf-8').strip()
                print(f"从Arduino接收: {monitor}")
                if monitor == "PLAYBACK":
                    print("play")
                    self.start_playback()
                elif monitor == "SWITCH":
                    print("switch")
                    self.toggle_switch()
                elif monitor == "ENDRECORDING":
                    print("endrecording")
                    self.end_recording()        

    def update_reverb(self, value):
        """更新混响强度并记录变化"""
        new_value = float(value)
        if self.reverb_room_size != new_value:
            self.reverb_room_size = new_value
            self.reverb_room_size_display.config(text=f"{new_value:.2f}")
            self.reverb.room_size = new_value
            self.record_effect_change('reverb_room_size', new_value)

    def update_distortion(self, value):
        """更新失真度并记录变化"""
        new_value = float(value)
        if self.distortion_level != new_value:
            self.distortion_level = new_value
            self.distortion_level_display.config(text=f"{new_value:.2f}")
            self.distortion.drive_db = new_value * 40  # 将0-1的范围映射到0-40dB
            self.record_effect_change('distortion_level', new_value)

    def update_delay_time(self, value):
        """更新延迟时间并记录变化"""
        new_value = float(value)
        if self.delay_time != new_value:
            self.delay_time = new_value
            self.delay_time_display.config(text=f"{new_value:.2f}")
            self.delay.delay_seconds = new_value
            self.record_effect_change('delay_time', new_value)

    def update_delay_feedback(self, value):
        """更新延迟反馈并记录变化"""
        new_value = float(value)
        if self.delay_feedback != new_value:
            self.delay_feedback = new_value
            self.delay_feedback_display.config(text=f"{new_value:.2f}")
            self.delay.feedback = new_value
            self.record_effect_change('delay_feedback', new_value)

    def update_chorus_rate(self, value):
        """更新和声速率并记录变化"""
        new_value = float(value)
        if self.chorus_rate != new_value:
            self.chorus_rate = new_value
            self.chorus_rate_display.config(text=f"{new_value:.1f}")
            self.chorus.rate_hz = new_value
            self.record_effect_change('chorus_rate', new_value)   

    def update_chorus_depth(self, value):
        """更新和声深度并记录变化"""
        new_value = float(value)
        if self.chorus_depth != new_value:
            self.chorus_depth = new_value
            self.chorus_depth_display.config(text=f"{new_value:.1f}")
            self.chorus.depth = new_value
            self.record_effect_change('chorus_depth', new_value)           

    def update_compressor_threshold(self, value):
        """更新压缩强度并记录变化"""
        new_value = float(value)
        if self.compressor_threshold != new_value:
            self.compressor_threshold = new_value
            self.compressor_threshold_display.config(text=f"{new_value:.1f}")
            self.compressor.threshold_db = new_value
            self.record_effect_change('compressor_threshold', new_value)  

    def update_compressor_ratio(self, value):
        """更新压缩比率并记录变化"""
        new_value = float(value)
        if self.compressor_ratio != new_value:
            self.compressor_ratio = new_value
            self.compressor_ratio_display.config(text=f"{new_value:.1f}")
            self.compressor.ratio = new_value
            self.record_effect_change('compressor_ratio', new_value)           

    def update_phaser_rate(self, value):
        """更新相位速率并记录变化"""
        new_value = float(value)
        if self.phaser_rate != new_value:
            self.phaser_rate = new_value
            self.phaser_rate_display.config(text=f"{new_value:.1f}")
            self.phaser.rate_hz = new_value
            self.record_effect_change('phaser_rate', new_value)  

    def update_phaser_feedback(self, value):
        """更新相位回授并记录变化"""
        new_value = float(value)
        if self.phaser_feedback != new_value:
            self.phaser_feedback = new_value
            self.phaser_feedback_display.config(text=f"{new_value:.1f}")
            self.phaser.feedback = new_value
            self.record_effect_change('phaser_feedback', new_value)            

    def update_master_mix(self, value):
        """更新主输出MIX并记录变化"""
        new_value = float(value)
        if self.master_mix != new_value:
            self.master_mix = new_value
            self.master_mix_display.config(text=f"{new_value:.2f}")
            self.record_effect_change('master_mix', new_value)

    def update_bitcrush(self, value):
        """更新Bitcrush位深度并记录变化"""
        new_value = float(value)
        if self.bitcrush_bits != new_value:
            self.bitcrush_bits = new_value
            self.bitcrush_bits_display.config(text=f"{new_value:.1f}")
            self.bitcrush.bit_depth = new_value
            self.record_effect_change('bitcrush_bits', new_value)

    def update_effect_parameter(self, effect_type, value):
        """更新特定效果的参数"""
        if effect_type == 'reverb_room_size':
            self.reverb_room_size = value
            self.reverb.room_size = value
            self.update_reverb(value)
        elif effect_type == 'distortion_level':
            self.distortion_level = value
            self.distortion.drive_db = value * 40
            self.update_distortion(value)
        elif effect_type == 'delay_time':
            self.delay_time = value
            self.delay.delay_seconds = value
            self.update_delay_time(value)
        elif effect_type == 'delay_feedback':
            self.delay_feedback = value
            self.delay.feedback = value
            self.update_delay_feedback(value)
        elif effect_type == 'compressor_threshold':
            self.compressor_threshold = value
            self.compressor.threshold_db = value  
            self.update_compressor_threshold(value)
        elif effect_type == 'chorus_rate':
            self.chorus_rate = value
            self.chorus.rate_hz = value
            self.update_chorus_rate(value)
        elif effect_type == 'phaser_rate':
            self.phaser_rate = value
            self.phaser_rate_hz = value 
            self.update_phaser_rate(value)
        elif effect_type == 'master_mix':
            self.master_mix = value
            self.update_master_mix(value)
        elif effect_type == 'bitcrush_bits':
            self.bitcrush_bits = value
            self.bitcrush.bit_depth = value
            self.update_bitcrush(value)
        elif effect_type == 'compressor_threshold':
            self.compressor_threshold = value
            self.compressor.threshold_db = value 
            self.update_compressor_threshold(value)
        elif effect_type == 'compressor_ratio':
            self.compressor_ratio = value
            self.compressor.ratio = value
            self.update_compressor_ratio(value)
        elif effect_type == 'chorus_rate':
            self.chorus_rate = value
            self.chorus.rate_hz = value
            self.update_chorus_rate(value)
        elif effect_type == 'chorus_depth':
            self.chorus_depth = value
            self.chorus.depth = value
            self.update_chorus_depth(value)
        elif effect_type == 'phaser_rate':
            self.phaser_rate = value
            self.phaser.rate_hz = value
            self.update_phaser_rate(value)
        elif effect_type == 'phaser_feedback':
            self.phaser_feedback = value
            self.phaser.depth = value
            self.update_phaser_feedback(value)


    def record_effect_change(self, effect_type, value):
        """记录效果参数变化及相对于音频开始的时间点"""
        current_time = self.file_position / self.sample_rate if self.audio_data is not None else 0
        self.effect_history[effect_type].append((current_time, value))

    def get_effect_at_time(self, effect_type, time_point):
        """获取指定时间点的效果参数值"""
        history = self.effect_history[effect_type]
        # 找到最新的参数变化
        for i in range(len(history) - 1, -1, -1):
            if history[i][0] <= time_point:
                return history[i][1]
        return history[0][1]  # 如果没有找到，返回初始值

    def reset_effects(self):
        """重置所有效果参数"""
        self.reverb_room_size = 0.0
        self.distortion_level = 0.0
        self.delay_time = 0.0
        self.delay_feedback = 0.0
        self.master_mix = 0.2
        self.bitcrush_bits = 8.0
        self.compressor_threshold = 0.0
        self.compressor_ratio = 1.0 
        self.chorus_rate = 0.0  
        self.chorus_depth = 0.0   
        self.phaser_rate = 0.0   
        self.phaser_feedback = 0.0

        # 更新UI
        self.reverb_room_size_value.set(self.reverb_room_size)
        self.distortion_level_value.set(self.distortion_level)
        self.delay_time_value.set(self.delay_time)
        self.delay_feedback_value.set(self.delay_feedback)
        self.master_mix_value.set(self.master_mix)
        self.bitcrush_bits_value.set(self.bitcrush_bits)
        self.compressor_threshold_value.set(self.compressor_threshold)
        self.compressor_ratio_value.set(self.compressor_ratio) 
        self.chorus_rate_value.set(self.chorus_rate)
        self.chorus_depth_value.set(self.chorus_depth)    
        self.phaser_rate_value.set(self.phaser_rate)
        self.phaser_feedback_value.set(self.phaser_feedback)

        # 更新效果参数
        self.reverb.room_size = self.reverb_room_size
        self.distortion.drive_db = self.distortion_level * 40
        self.delay.delay_seconds = self.delay_time
        self.delay.feedback = self.delay_feedback
        self.bitcrush.bit_depth = self.bitcrush_bits
        self.compressor.threshold_db = self.compressor_threshold
        self.compressor.ratio = self.compressor_ratio
        self.chorus.rate_hz = self.chorus_rate
        self.chorus.depth = self.chorus_depth   
        self.phaser.rate_hz = self.phaser_rate
        self.phaser.depth = self.phaser_feedback
        # 重置效果历史
        self.reset_effect_history()

        self.status_var.set("效果已重置")

    def reset_effect_history(self):
        """重置效果历史记录"""
        current_time = self.file_position / self.sample_rate if self.audio_data is not None else 0
        self.effect_history = {
            'reverb_room_size': [(current_time, self.reverb_room_size)],
            'distortion_level': [(current_time, self.distortion_level)],
            'delay_time': [(current_time, self.delay_time)],
            'delay_feedback': [(current_time, self.delay_feedback)],
            'master_mix': [(current_time, self.master_mix)],
            'bitcrush_bits': [(current_time, self.bitcrush_bits)],
            'compressor_threshold': [(current_time, self.compressor_threshold)],
            'compressor_ratio': [(current_time, self.compressor_ratio)],
            'chorus_rate': [(current_time, self.chorus_rate)],
            'chorus_depth': [(current_time, self.chorus_depth)],
            'phaser_rate': [(current_time, self.phaser_rate)],
            'phaser_feedback': [(current_time, self.phaser_feedback)]

        }

    

        
    def end_recording(self):    
        if self.is_recording:
            self.is_recording = False
            self.save_recorded_audio()
            if self.is_playing:
                 self.is_playing = False
                 self.stop_playback()
            if self.stream and self.stream.active:
                try:
                    self.stream.stop()
                    self.stream.close()
                except Exception as e:
                       print(f"关闭流时出错: {e}")


    def save_recorded_audio(self):
        if not self.recorded_data:
            messagebox.showinfo("提示", "没有录制到音频")
            return

        save_path = filedialog.asksaveasfilename(
            title="保存录制的音频",
            defaultextension=".wav",
            filetypes=[("WAV文件", "*.wav"), ("FLAC文件", "*.flac")]
        )

        if not save_path:
            return

        try:
            recorded_audio = np.concatenate(self.recorded_data, axis=0)
            sf.write(save_path, recorded_audio, self.sample_rate)
            messagebox.showinfo("成功", f"已保存录制的音频至:\n{save_path}")
            self.status_var.set("录制音频保存成功")
        except Exception as e:
            messagebox.showerror("错误", f"保存录制的音频失败: {str(e)}")
            self.status_var.set("录制音频保存失败")

    def on_closing(self):
        """处理窗口关闭事件"""
        if self.is_playing:
            self.stop_playback()

        if self.stream and self.stream.active:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception as e:
                print(f"关闭流时出错: {e}")

        self.root.destroy()

    def loop_adjust_effects(self):
        self.adjust_effects_based_on_emotion()
        self.root.after(100, self.loop_adjust_effects)
    
    def adjust_effects_based_on_emotion(self):
        # 定义每个表情对应的音效参数目标值和步进量
        self.last_effect_operation = None  # 初始化为None，表示还没有执行过任何操作
        emotion_effect_mapping = {
        "neutral": {
            "reverb_room_size": (0.0, 0.005),
            "distortion_level": (0.0, 0.005),
            "delay_time": (0.0, 0.005),
            "delay_feedback": (0.0, 0.005),
            "master_mix": (0.2, 0.005),
            "bitcrush_bits": (8.0, 0.05),
            "compressor_threshold": (-60.0, 0.05),
            "compressor_ratio": (1.0, 0.05),
            "chorus_rate": (0.0, 0.005),
            "chorus_depth": (0.0, 0.005),
            "phaser_rate": (0.0, 0.005),
            "phaser_feedback": (0.0, 0.005)
        },
        "happy": {
            "reverb_room_size": (0.0, 0.01),
            "delay_time": (0.0, 0.01),
            "delay_feedback": (0.0, 0.01),
            "compressor_threshold": (0.0, 0.1),
            "chorus_depth": (0.2, 0.01),
            "master_mix": (0.25, 0.01),
            "compressor_ratio": (1.0, 0.1),
            "bitcrush_bits": (10.0, 0.2),
            "chorus_rate": (0.5, 0.01),
            "phaser_rate": (0.65, 0.01),
            "phaser_feedback": (-0.35, 0.01)
        },
        "floating": {
            "reverb_room_size": (0.9, 0.03),
            "distortion_level": (0.0, 0.01),
            "delay_time": (1.5, 0.01),
            "delay_feedback": (1.0, 0.02),
            "compressor_threshold": (-20.0, 0.1),
            "compressor_ratio": (3.0, 0.1),
            "chorus_rate": (1.2, 0.01),
            "chorus_depth": (0.8, 0.01),
            "master_mix": (1.0, 0.02),
            "bitcrush_bits": (5.5, 0.1),
            "phaser_rate": (0.1, 0.01),
            "phaser_feedback": (0.10, 0.01)
        },
        "aggressive": {
            "reverb_room_size": (0.35, 0.01),
            "distortion_level": (1.0, 0.01),
            "delay_time": (0.2, 0.01),
            "delay_feedback": (0.3, 0.01),
            "bitcrush_bits": (3.5, 0.1),
            "compressor_threshold": (0.0, 0.1),
            "compressor_ratio": (1.0, 0.1),
            "chorus_rate": (0.0, 0.01),
            "chorus_depth": (0.0, 0.01),
            "master_mix": (1.0, 0.01),
            "phaser_rate": (2.0, 0.01),
            "phaser_feedback": (0.65, 0.01)
        },
        "enjoyed": {
            "reverb_room_size": (0.5, 0.01),
            "delay_time": (0.15, 0.01),
            "delay_feedback": (0.2, 0.01),
            "compressor_threshold": (0.0, 0.1),
            "compressor_ratio": (1.0, 0.1),
            "chorus_rate": (0.3, 0.01),
            "chorus_depth": (0.6, 0.01),
            "master_mix": (0.5, 0.01),
            "bitcrush_bits": (10.0, 0.1),
            "phaser_feedback": (-0.10, 0.01)
        },
        "followbeats": {
            "reverb_room_size": (0.0, 0.01),
            "distortion_level": (0.4, 0.01),
            "delay_time": (0.0, 0.01),
            "delay_feedback": (0.0, 0.01),
            "bitcrush_bits": (6.0, 0.1),
            "compressor_threshold": (-30.0, 0.1),
            "compressor_ratio": (8.0, 0.1),
            "chorus_rate": (0.3, 0.01),
            "chorus_depth": (0.4, 0.01),
            "master_mix": (0.6, 0.01),
            "phaser_rate": (0.4, 0.01),
            "phaser_feedback": (0.2, 0.01)
        },
        "sad": {
            "reverb_room_size": (0.7, 0.01),
            "distortion_level": (0.1, 0.01),
            "delay_time": (0.3, 0.01),
            "delay_feedback": (0.3, 0.01),
            "bitcrush_bits": (6.2, 0.1),
            "compressor_threshold": (-30.0, 0.1),
            "compressor_ratio": (3.0, 0.1),
            "chorus_rate": (0.1, 0.01),
            "chorus_depth": (0.2, 0.01),
            "master_mix": (0.4, 0.01),
            "phaser_rate": (0.0, 0.01),
            "phaser_feedback": (0.0, 0.01)
        },
        "sad2": {
            "reverb_room_size": (0.7, 0.02),
            "distortion_level": (0.5, 0.01),
            "delay_time": (0.3, 0.01),
            "delay_feedback": (0.3, 0.01),
            "bitcrush_bits": (6.2, 0.1),
            "compressor_threshold": (-10.0, 0.1),
            "compressor_ratio": (2.0, 0.1),
            "chorus_rate": (0.25, 0.01),
            "chorus_depth": (0.4, 0.01),
            "master_mix": (0.6, 0.01),
            "phaser_rate": (0.0, 0.01),
            "phaser_feedback": (0.0, 0.01)
        },
        "scream": {
            "reverb_room_size": (0.7, 0.02),
            "distortion_level": (1.0, 0.02),
            "delay_time": (0.3, 0.01),
            "delay_feedback": (0.3, 0.01),
            "bitcrush_bits": (5.9, 0.1),
            "compressor_threshold": (0.0, 0.1),
            "compressor_ratio": (1.0, 0.1),
            "chorus_rate": (0.45, 0.01),
            "chorus_depth": (0.55, 0.01),
            "master_mix": (1.0, 0.01),
            "phaser_rate": (0.0, 0.01),
            "phaser_feedback": (0.0, 0.01)
        },
        "immersed": {
            "master_mix": (1.0, 0.01)
        }}
        
        if not os.path.exists('emotion.txt'):
            with open('emotion.txt', 'w') as f:
                f.write("初始化中...")   
        emotion = get_emotion()
        
        if emotion == "immersed" and self.last_effect_operation:
            # 重复上次的音效操作
            for effect_type, (target, step) in self.last_effect_operation.items():
                current_value = getattr(self, f"{effect_type}")
                if current_value != target:
                    if current_value < target:
                        new_value = min(current_value + step, target)
                    else:
                        new_value = max(current_value - step, target)
                    self.update_effect_parameter(effect_type, new_value)
                    self.record_effect_change(effect_type, new_value)

            # 同时mix向1趋近
            target, step = emotion_effect_mapping["immersed"]["master_mix"]
            current_value = self.master_mix
            if current_value != target:
                if current_value < target:
                    
                    new_value = min(current_value + step, target)
                    
                else:
                   
                    new_value = max(current_value - step, target)
                   
                self.update_master_mix(new_value)
                self.record_effect_change("master_mix", new_value)
        elif emotion in emotion_effect_mapping:
            
            self.last_effect_operation = emotion_effect_mapping[emotion]
            for effect_type, (target, step) in emotion_effect_mapping[emotion].items():
                current_value = getattr(self, f"{effect_type}")
                
                if current_value != target:
                    
                    if current_value < target:
                        
                        new_value = min(current_value + step, target)
                        
                    else:
                        
                        new_value = max(current_value - step, target)
                    self.update_effect_parameter(effect_type, new_value)
                    self.record_effect_change(effect_type, new_value)
            
if __name__ == "__main__":
    app = AudioProcessor()
    