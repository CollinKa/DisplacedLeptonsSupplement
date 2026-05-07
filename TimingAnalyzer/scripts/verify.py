import argparse
import uproot

from DisplacedLeptonsNanoSupplement.TimingAnalyzer.dataset_lumis import get_lumi_files

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("supplement_file")
    parser.add_argument("central_dataset")
    args = parser.parse_args()

    f = uproot.open(args.supplement_file)
    arrays = f["muonTimingAnalyzer/muonTree"].arrays(library="np")

    lumi_map = get_lumi_files(args.central_dataset)
    import pdb; pdb.set_trace()



if __name__ == "__main__":
    main()
