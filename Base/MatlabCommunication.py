import json

seq_info = dict(JeanFreq=89,
                FrancesFreq=71,
                commands=
                ["runfit(PixisRb,'gauss', 'fix', {'offset'}, 'ROI', [130 1; 1020 450], 'AutoROI', [400,400])",
                 "writetoOrigin(PixisRb,{'JeanFreq','FrancesFreq','repump_time','tof','Ntot','result'})",
                 "writetofile(PixisRb,{'tof'}, 'saveRAW', 1)",
                 "showres(PixisRb)"],
                window=1024,
                rawmode='normal',
                repump_time=0.3,
                detune_repump=0,
                cycle=0,
                timeLatest=49.423103,
                timeReload=64.395104,
                timeRestart=69.395104,
                tof=8,
                evap_final=8)


def write():
    file = json.dumps(seq_info)
    f = open("Z:/Code/fitter/seq-Rb.json", "w")
    f.write(file)
    f.close()
