#ifndef DisplacedLeptonsNanoSupplement_TimingAnalyzer_MuonTimingAnalyzer_h
#define DisplacedLeptonsNanoSupplement_TimingAnalyzer_MuonTimingAnalyzer_h

#include "CommonTools/UtilAlgos/interface/TFileService.h"
#include "DataFormats/PatCandidates/interface/Electron.h"
#include "DataFormats/PatCandidates/interface/Muon.h"
#include "FWCore/Framework/interface/EDAnalyzer.h"
#include "FWCore/Framework/interface/Event.h"
#include "FWCore/ParameterSet/interface/ParameterSet.h"
#include "FWCore/ServiceRegistry/interface/Service.h"
#include "FWCore/Utilities/interface/EDGetToken.h"
#include "TTree.h"
#include <vector>

class MuonTimingAnalyzer : public edm::EDAnalyzer {
public:
  explicit MuonTimingAnalyzer(const edm::ParameterSet &);
  ~MuonTimingAnalyzer() {}

private:
  void beginJob() override;
  void analyze(const edm::Event &, const edm::EventSetup &) override;

  // Both consumed directly from MiniAOD; selection applied in analyze()
  edm::EDGetTokenT<std::vector<pat::Muon>>     muonToken_;
  edm::EDGetTokenT<std::vector<pat::Electron>> electronToken_;

  edm::Service<TFileService> fs_;
  TTree *tree_;

  UInt_t    run_;
  UInt_t    lumi_;
  ULong64_t event_;

  // Per-muon branches (one entry per NanoAOD-indexed muon)
  std::vector<float> muon_pt_;
  std::vector<float> muon_eta_;
  std::vector<float> muon_phi_;
  std::vector<float> muon_timeAtIpInOut_;
  std::vector<int>   muon_timeNDof_;

  // Per-electron branches (one entry per NanoAOD-indexed electron)
  std::vector<float> electron_pt_;
  std::vector<float> electron_eta_;
  std::vector<float> electron_phi_;
};

#endif
