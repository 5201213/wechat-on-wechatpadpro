import os
import shutil
import wave

from common.log import logger

try:
    import pysilk
except ImportError:
    logger.debug("import pysilk failed, wechaty voice message will not be supported.")

try:
    from pydub import AudioSegment
except ImportError:
    logger.warning("import pydub failed, wechat voice conversion will not be supported. Try: pip install pydub")

try:
    import pilk
except ImportError:
    logger.warning("import pilk failed, silk voice conversion will not be supported. Try: pip install pilk")

sil_supports = [8000, 12000, 16000, 24000, 32000, 44100, 48000]  # slk转wav时，支持的采样率


def find_closest_sil_supports(sample_rate):
    """
    找到最接近的支持的采样率
    """
    if sample_rate in sil_supports:
        return sample_rate
    closest = 0
    mindiff = 9999999
    for rate in sil_supports:
        diff = abs(rate - sample_rate)
        if diff < mindiff:
            closest = rate
            mindiff = diff
    return closest


def get_pcm_from_wav(wav_path):
    """
    从 wav 文件中读取 pcm

    :param wav_path: wav 文件路径
    :returns: pcm 数据
    """
    wav = wave.open(wav_path, "rb")
    return wav.readframes(wav.getnframes())


def any_to_mp3(any_path, mp3_path):
    """
    把任意格式转成mp3文件

    Args:
        any_path: 输入文件路径
        mp3_path: 输出的mp3文件路径
    """
    try:
        # 如果已经是mp3格式，直接复制
        if any_path.endswith(".mp3"):
            shutil.copy2(any_path, mp3_path)
            return

        # 如果是silk格式，使用pilk转换
        if any_path.endswith((".sil", ".silk", ".slk")):
            # 先转成PCM
            pcm_path = any_path + '.pcm'
            pilk.decode(any_path, pcm_path)

            # 再用pydub把PCM转成MP3
            # TODO: 下面的参数可能需要调整
            audio = AudioSegment.from_raw(pcm_path, format="raw",
                                        frame_rate=24000,
                                        channels=1,
                                        sample_width=2)  # 16-bit PCM = 2 bytes
            audio.export(mp3_path, format="mp3")

            # 清理临时PCM文件
            import os
            os.remove(pcm_path)
            return

        # 其他格式使用pydub转换
        audio = AudioSegment.from_file(any_path)
        audio.export(mp3_path, format="mp3")

    except Exception as e:
        logger.error(f"转换文件到mp3失败: {str(e)}")
        raise


def any_to_wav(any_path, wav_path):
    """
    把任意格式转成wav文件
    """
    if any_path.endswith(".wav"):
        shutil.copy2(any_path, wav_path)
        return
    if any_path.endswith(".sil") or any_path.endswith(".silk") or any_path.endswith(".slk"):
        return sil_to_wav(any_path, wav_path)
    audio = AudioSegment.from_file(any_path)
    audio.set_frame_rate(8000)    # 百度语音转写支持8000采样率, pcm_s16le, 单通道语音识别
    audio.set_channels(1)
    audio.export(wav_path, format="wav", codec='pcm_s16le')


def any_to_sil(any_path, sil_path):
    """
    把任意格式转成sil文件 - 优化音质版本
    """
    if any_path.endswith(".sil") or any_path.endswith(".silk") or any_path.endswith(".slk"):
        shutil.copy2(any_path, sil_path)
        return 10000

    audio = AudioSegment.from_file(any_path)

    # 优化音质设置：强制使用48000Hz采样率以获得最佳音质
    # SILK支持的最高采样率，提供最佳音质
    target_rate = 48000

    logger.info(f"[SILK转换] 原始采样率: {audio.frame_rate}Hz -> 目标采样率: {target_rate}Hz")

    # 转换为高质量PCM格式
    # 1. 设置为单声道（微信语音要求）
    audio = audio.set_channels(1)
    # 2. 设置为16位采样深度
    audio = audio.set_sample_width(2)
    # 3. 设置为48000Hz高采样率
    audio = audio.set_frame_rate(target_rate)

    # 获取PCM数据
    wav_data = audio.raw_data

    # 使用pysilk编码为SILK格式
    silk_data = pysilk.encode(wav_data, data_rate=target_rate, sample_rate=target_rate)

    with open(sil_path, "wb") as f:
        f.write(silk_data)

    logger.info(f"[SILK转换] 转换完成: {any_path} -> {sil_path}, 采样率: {target_rate}Hz")
    return audio.duration_seconds * 1000

def mp3_to_silk(mp3_path: str, silk_path: str) -> int:
    """Convert MP3 file to SILK format - 高音质版本
    Args:
        mp3_path: Path to input MP3 file
        silk_path: Path to output SILK file
    Returns:
        Duration of the SILK file in milliseconds
    """
    # 加载MP3文件
    audio = AudioSegment.from_file(mp3_path)

    # 优化音质设置：使用48000Hz采样率
    target_rate = 48000
    logger.info(f"[SILK转换] MP3原始采样率: {audio.frame_rate}Hz -> 目标采样率: {target_rate}Hz")

    # 转换为高质量格式
    audio = audio.set_channels(1)  # 单声道
    audio = audio.set_sample_width(2)  # 16位
    audio = audio.set_frame_rate(target_rate)  # 48000Hz高采样率

    # 导出为PCM格式
    pcm_path = os.path.splitext(mp3_path)[0] + '.pcm'
    audio.export(pcm_path, format='s16le')

    # 使用pilk转换为SILK格式（高采样率）
    pilk.encode(pcm_path, silk_path, pcm_rate=target_rate, tencent=True)

    # 清理临时PCM文件
    os.remove(pcm_path)

    # 获取SILK文件时长
    duration = pilk.get_duration(silk_path)
    logger.info(f"[SILK转换] MP3转换完成: {mp3_path} -> {silk_path}, 采样率: {target_rate}Hz")
    return duration

def any_to_amr(any_path, amr_path):
    """
    把任意格式转成amr文件
    """
    if any_path.endswith(".amr"):
        shutil.copy2(any_path, amr_path)
        return
    if any_path.endswith(".sil") or any_path.endswith(".silk") or any_path.endswith(".slk"):
        raise NotImplementedError("Not support file type: {}".format(any_path))
    audio = AudioSegment.from_file(any_path)
    audio = audio.set_frame_rate(8000)  # only support 8000
    audio.export(amr_path, format="amr")
    return audio.duration_seconds * 1000

# TODO: 删除pysilk，改用pilk
def sil_to_wav(silk_path, wav_path, rate: int = 24000):
    """
    silk 文件转 wav
    """
    wav_data = pysilk.decode_file(silk_path, to_wav=True, sample_rate=rate)
    with open(wav_path, "wb") as f:
        f.write(wav_data)


def split_audio(file_path, max_segment_length_ms=60000):
    """
    分割音频文件
    """
    audio = AudioSegment.from_file(file_path)
    audio_length_ms = len(audio)
    if audio_length_ms <= max_segment_length_ms:
        return audio_length_ms, [file_path]
    segments = []
    for start_ms in range(0, audio_length_ms, max_segment_length_ms):
        end_ms = min(audio_length_ms, start_ms + max_segment_length_ms)
        segment = audio[start_ms:end_ms]
        segments.append(segment)
    file_prefix = file_path[: file_path.rindex(".")]
    format = file_path[file_path.rindex(".") + 1 :]
    files = []
    for i, segment in enumerate(segments):
        path = f"{file_prefix}_{i+1}" + f".{format}"
        segment.export(path, format=format)
        files.append(path)
    return audio_length_ms, files
