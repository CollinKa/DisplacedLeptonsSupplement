#include "FWCore/Framework/interface/Frameworkfwd.h"
#include "FWCore/Framework/interface/one/EDAnalyzer.h"
#include "FWCore/Framework/interface/Event.h"
#include "FWCore/Framework/interface/MakerMacros.h"
#include "FWCore/ParameterSet/interface/ParameterSet.h"
#include "FWCore/ServiceRegistry/interface/Service.h"
#include "CommonTools/UtilAlgos/interface/TFileService.h"
#include "CommonTools/Utils/interface/StringObjectFunction.h"
#include "DataFormats/PatCandidates/interface/Muon.h"
#include "TTree.h"

class ExtractAnalyzer : public edm::one::EDAnalyzer<edm::one::SharedResources> {
public:
    explicit ExtractAnalyzer(const edm::ParameterSet& cfg);
    static void fillDescriptions(edm::ConfigurationDescriptions& descriptions);

private:
    void beginJob() override;
    void analyze(const edm::Event& event, const edm::EventSetup& setup) override;
    void endJob() override {}

    edm::EDGetTokenT<std::vector<pat::Muon>> srcToken_;
    double ptCut_;

    std::vector<std::string> varNames_;
    std::vector<StringObjectFunction<pat::Muon>> varFuncs_;
    std::vector<std::vector<float>> varValues_;

    edm::Service<TFileService> fs_;
    TTree* tree_;

    unsigned int run_;
    unsigned int lumi_;
    unsigned long long event_;
};

ExtractAnalyzer::ExtractAnalyzer(const edm::ParameterSet& cfg)
    : srcToken_(consumes<std::vector<pat::Muon>>(cfg.getParameter<edm::InputTag>("src"))),
      ptCut_(cfg.getParameter<double>("ptCut"))
{
    usesResource("TFileService");

    const edm::ParameterSet& varPset = cfg.getParameter<edm::ParameterSet>("variables");
    for (const auto& name : varPset.getParameterNames()) {
        varNames_.push_back(name);
        varFuncs_.emplace_back(varPset.getParameter<std::string>(name));
    }
    varValues_.resize(varNames_.size());
}

void ExtractAnalyzer::beginJob() {
    tree_ = fs_->make<TTree>("DisplacedMuons", "slimmedDisplacedMuons from MiniAOD");
    tree_->Branch("run",              &run_,   "run/i");
    tree_->Branch("luminosityBlock", &lumi_,  "luminosityBlock/i");
    tree_->Branch("event",           &event_, "event/l");
    for (size_t i = 0; i < varNames_.size(); i++)
        tree_->Branch(varNames_[i].c_str(), &varValues_[i]);
}

void ExtractAnalyzer::analyze(const edm::Event& event, const edm::EventSetup&) {
    edm::Handle<std::vector<pat::Muon>> muons;
    event.getByToken(srcToken_, muons);

    run_   = event.id().run();
    lumi_  = event.id().luminosityBlock();
    event_ = event.id().event();

    for (auto& v : varValues_) v.clear();

    for (const auto& mu : *muons) {
        if (mu.pt() < ptCut_) continue;
        for (size_t i = 0; i < varNames_.size(); i++)
            varValues_[i].push_back(varFuncs_[i](mu));
    }
    tree_->Fill();
}

void ExtractAnalyzer::fillDescriptions(edm::ConfigurationDescriptions& descriptions) {
    edm::ParameterSetDescription desc;
    desc.add<edm::InputTag>("src", edm::InputTag("slimmedDisplacedMuons"));
    desc.add<double>("ptCut", 15.0);
    edm::ParameterSetDescription varDesc;
    varDesc.setAllowAnything();
    desc.add<edm::ParameterSetDescription>("variables", varDesc);
    descriptions.addDefault(desc);
}

DEFINE_FWK_MODULE(ExtractAnalyzer);
